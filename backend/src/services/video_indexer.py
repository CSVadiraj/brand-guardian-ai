import logging
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
import yt_dlp
from azure.identity import DefaultAzureCredential

from backend.src.config import get_required_environment, load_project_environment

logger = logging.getLogger("video-indexer")


class VideoIndexerError(RuntimeError):
    """Raised when a Video Indexer operation fails."""


def is_supported_youtube_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed_url = urlsplit(url)
        hostname = (parsed_url.hostname or "").lower()
    except ValueError:
        return False
    return (
        parsed_url.scheme == "https"
        and parsed_url.username is None
        and parsed_url.password is None
        and bool(parsed_url.path.strip("/"))
        and (
        hostname == "youtu.be"
        or hostname.endswith(".youtu.be")
        or hostname == "youtube.com"
        or hostname.endswith(".youtube.com")
        )
    )


class VideoIndexerService:
    def __init__(self):
        load_project_environment()
        configuration = get_required_environment(
            "AZURE_VI_ACCOUNT_ID",
            "AZURE_VI_LOCATION",
            "AZURE_VI_SUBSCRIPTION_ID",
            "AZURE_RESOURCE_GROUP",
            "AZURE_VI_NAME",
        )
        self.account_id = configuration["AZURE_VI_ACCOUNT_ID"]
        self.location = configuration["AZURE_VI_LOCATION"]
        self.subscription_id = configuration["AZURE_VI_SUBSCRIPTION_ID"]
        self.resource_group = configuration["AZURE_RESOURCE_GROUP"]
        self.vi_name = configuration["AZURE_VI_NAME"]
        self.credential = DefaultAzureCredential()

    def get_access_token(self) -> str:
        """Get an ARM token using the configured Azure identity."""
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as exc:
            raise VideoIndexerError(
                "Azure authentication failed. Run 'az login' or configure a managed identity."
            ) from exc

    @staticmethod
    def _response_json(response: requests.Response, operation: str) -> dict:
        if not 200 <= response.status_code < 300:
            raise VideoIndexerError(
                f"Video Indexer {operation} failed (HTTP {response.status_code})."
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise VideoIndexerError(
                f"Video Indexer {operation} returned invalid JSON."
            ) from exc
        if not isinstance(data, dict):
            raise VideoIndexerError(
                f"Video Indexer {operation} returned an invalid response."
            )
        return data

    def get_account_token(self, arm_access_token: str) -> str:
        """Exchange an ARM token for an account-scoped Video Indexer token."""
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=(10, 30)
            )
        except requests.RequestException as exc:
            raise VideoIndexerError(
                "Video Indexer account-token request failed due to a network error."
            ) from exc
        data = self._response_json(response, "account-token request")
        token = data.get("accessToken")
        if not isinstance(token, str) or not token:
            raise VideoIndexerError(
                "Video Indexer account-token response did not contain an access token."
            )
        return token

    def download_youtube_video(self, url: str, output_path: str = "temp_video.mp4") -> str:
        """Download a YouTube video and return the actual file path."""
        if not is_supported_youtube_url(url):
            raise VideoIndexerError("A valid HTTPS YouTube video URL is required.")

        output = Path(output_path)
        template = str(output.with_suffix("")) + ".%(ext)s"
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": template,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_path = Path(ydl.prepare_filename(info))
            if not downloaded_path.is_file() or downloaded_path.stat().st_size == 0:
                raise VideoIndexerError("YouTube download produced no video file.")
            logger.info("YouTube video download completed.")
            return str(downloaded_path)
        except VideoIndexerError:
            raise
        except Exception as exc:
            logger.error("YouTube download failed (%s).", type(exc).__name__)
            raise VideoIndexerError(
                f"YouTube download failed ({type(exc).__name__})."
            ) from exc

    def upload_video(self, video_path: str, video_name: str) -> str:
        """Upload a local video file to Azure Video Indexer."""
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }
        path = Path(video_path)
        if not path.is_file():
            raise VideoIndexerError("The downloaded video file does not exist.")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as video_file:
                response = requests.post(
                    api_url,
                    params=params,
                    files={"file": (path.name, video_file, content_type)},
                    timeout=(15, 300),
                )
        except requests.RequestException as exc:
            raise VideoIndexerError(
                "Video Indexer upload failed due to a network error."
            ) from exc
        data = self._response_json(response, "upload")
        video_id = data.get("id")
        if not isinstance(video_id, str) or not video_id:
            raise VideoIndexerError(
                "Video Indexer upload response did not contain a video ID."
            )
        logger.info("Video upload completed.")
        return video_id

    def wait_for_processing(
        self,
        video_id: str,
        poll_interval: float = 30,
        timeout: float = 3600,
    ) -> dict:
        """Poll indexing status until completion or the timeout is reached."""
        if poll_interval <= 0 or timeout <= 0:
            raise ValueError("poll_interval and timeout must be greater than zero.")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)
            url = (
                f"https://api.videoindexer.ai/{self.location}/Accounts/"
                f"{self.account_id}/Videos/{video_id}/Index"
            )
            params = {"accessToken": vi_token}
            try:
                response = requests.get(url, params=params, timeout=(10, 30))
            except requests.RequestException as exc:
                raise VideoIndexerError(
                    "Video Indexer status request failed due to a network error."
                ) from exc
            data = self._response_json(response, "status request")

            processing_state = data.get("state")
            if processing_state == "Processed":
                return data
            if processing_state == "Failed":
                raise VideoIndexerError("Azure Video Indexer failed to process the video.")
            if processing_state == "Quarantined":
                raise VideoIndexerError("Azure Video Indexer quarantined the video.")

            remaining = deadline - time.monotonic()
            if remaining > 0:
                logger.info("Video Indexer state: %s; polling again.", processing_state)
                time.sleep(min(poll_interval, remaining))

        raise VideoIndexerError(
            f"Azure Video Indexer did not finish within {timeout:g} seconds."
        )

    def extract_data(self, vi_json: dict) -> dict:
        """Extract transcript, OCR text, and metadata from Video Indexer JSON."""
        transcript_lines = []
        ocr_lines = []
        videos = vi_json.get("videos", [])
        if not isinstance(videos, list):
            raise VideoIndexerError("Video Indexer returned an invalid videos field.")

        for video in videos:
            if not isinstance(video, dict):
                continue
            insights = video.get("insights", {})
            if not isinstance(insights, dict):
                continue
            transcript = insights.get("transcript", [])
            if not isinstance(transcript, list):
                transcript = []
            for entry in transcript:
                if isinstance(entry, dict):
                    text = entry.get("text")
                    if isinstance(text, str) and text.strip():
                        transcript_lines.append(text.strip())
            ocr = insights.get("ocr", [])
            if not isinstance(ocr, list):
                ocr = []
            for entry in ocr:
                if isinstance(entry, dict):
                    text = entry.get("text")
                    if isinstance(text, str) and text.strip():
                        ocr_lines.append(text.strip())

        summarized_insights = vi_json.get("summarizedInsights", {})
        if not isinstance(summarized_insights, dict):
            summarized_insights = {}
        duration = summarized_insights.get("duration", {})
        if not isinstance(duration, dict):
            duration = {}

        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": duration.get("seconds"),
                "platform": "youtube",
            },
        }