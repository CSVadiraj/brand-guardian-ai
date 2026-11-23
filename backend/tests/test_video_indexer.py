import os
import unittest
from unittest.mock import patch

from backend.src.services.video_indexer import (
    VideoIndexerError,
    VideoIndexerService,
    is_supported_youtube_url,
)


class VideoIndexerTests(unittest.TestCase):
    def test_youtube_url_validation_rejects_lookalike_hosts(self):
        self.assertTrue(is_supported_youtube_url("https://youtu.be/example"))
        self.assertTrue(is_supported_youtube_url("https://www.youtube.com/watch?v=example"))
        self.assertFalse(is_supported_youtube_url("http://youtu.be/example"))
        self.assertFalse(is_supported_youtube_url("https://youtu.be"))
        self.assertFalse(is_supported_youtube_url("https://user@youtu.be/example"))
        self.assertFalse(is_supported_youtube_url("https://youtube.com.attacker.invalid/video"))
        self.assertFalse(is_supported_youtube_url("https://example.com/video"))

    def test_subscription_id_uses_video_indexer_environment_name(self):
        configuration = {
            "AZURE_VI_ACCOUNT_ID": "account",
            "AZURE_VI_LOCATION": "region",
            "AZURE_VI_SUBSCRIPTION_ID": "subscription",
            "AZURE_RESOURCE_GROUP": "resource-group",
            "AZURE_VI_NAME": "account-name",
        }
        with patch.dict(os.environ, configuration, clear=True):
            with patch(
                "backend.src.services.video_indexer.DefaultAzureCredential"
            ):
                service = VideoIndexerService()
        self.assertEqual(service.subscription_id, "subscription")

    def test_extract_data_handles_missing_and_non_text_entries(self):
        service = object.__new__(VideoIndexerService)
        extracted = service.extract_data(
            {
                "videos": [
                    {
                        "insights": {
                            "transcript": [
                                {"text": " Spoken claim "},
                                {"text": None},
                                {"text": 42},
                            ],
                            "ocr": [{"text": " On-screen claim "}, {}],
                        }
                    }
                ],
                "summarizedInsights": {"duration": {"seconds": 12}},
            }
        )
        self.assertEqual(extracted["transcript"], "Spoken claim")
        self.assertEqual(extracted["ocr_text"], ["On-screen claim"])
        self.assertEqual(extracted["video_metadata"]["duration"], 12)

    def test_wait_for_processing_returns_processed_video(self):
        service = object.__new__(VideoIndexerService)
        service.location = "region"
        service.account_id = "account"
        with (
            patch.object(service, "get_access_token", return_value="arm-token"),
            patch.object(service, "get_account_token", return_value="account-token"),
            patch(
                "backend.src.services.video_indexer.requests.get",
                return_value=_FakeResponse({"state": "Processed"}),
            ),
        ):
            result = service.wait_for_processing(
                "video-id", poll_interval=0.001, timeout=1
            )
        self.assertEqual(result["state"], "Processed")

    def test_wait_for_processing_stops_on_failed_state(self):
        service = object.__new__(VideoIndexerService)
        service.location = "region"
        service.account_id = "account"
        with (
            patch.object(service, "get_access_token", return_value="arm-token"),
            patch.object(service, "get_account_token", return_value="account-token"),
            patch(
                "backend.src.services.video_indexer.requests.get",
                return_value=_FakeResponse({"state": "Failed"}),
            ),
        ):
            with self.assertRaisesRegex(VideoIndexerError, "failed to process"):
                service.wait_for_processing("video-id", timeout=1)


class _FakeResponse:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


if __name__ == "__main__":
    unittest.main()
