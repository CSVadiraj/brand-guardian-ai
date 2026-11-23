import json
import os
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage

from backend.src.graph.nodes import (
    _parse_audit_result,
    audit_content_node,
    index_video_node,
)


class NodeTests(unittest.TestCase):
    def test_index_node_rejects_non_youtube_urls_without_initializing_services(self):
        with patch("backend.src.graph.nodes.VideoIndexerService") as service_class:
            result = index_video_node({"video_url": "https://example.com/video"})
        service_class.assert_not_called()
        self.assertEqual(result["final_status"], "FAIL")
        self.assertIn("YouTube", result["errors"][0])

    def test_index_node_removes_temporary_video_after_upload(self):
        service = Mock()

        def write_download(_url, output_path):
            with open(output_path, "wb") as downloaded:
                downloaded.write(b"video")
            return output_path

        service.download_youtube_video.side_effect = write_download
        service.upload_video.return_value = "azure-video-id"
        service.wait_for_processing.return_value = {"videos": []}
        service.extract_data.return_value = {
            "transcript": "Claim",
            "ocr_text": [],
            "video_metadata": {},
        }
        with patch(
            "backend.src.graph.nodes.VideoIndexerService", return_value=service
        ):
            result = index_video_node(
                {
                    "video_url": "https://youtu.be/example",
                    "video_id": "test-video",
                }
            )
        downloaded_path = service.upload_video.call_args.args[0]
        self.assertFalse(os.path.exists(downloaded_path))
        self.assertEqual(result["transcript"], "Claim")

    def test_parser_accepts_fenced_json_and_does_not_allow_false_pass(self):
        response = _parse_audit_result(
            '```json\n{"status":"PASS","compliance_results":['
            '{"category":"Disclosure","severity":"warning",'
            '"description":"Missing disclosure"}],"final_report":"Review."}\n```'
        )
        self.assertEqual(response["final_status"], "FAIL")
        self.assertEqual(response["compliance_results"][0]["severity"], "WARNING")

    def test_parser_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            _parse_audit_result("not-json")

    @patch.dict(
        os.environ,
        {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
            "AZURE_OPENAI_API_VERSION": "test-version",
            "AZURE_OPENAI_CHAT_DEPLOYMENT": "test-chat",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "test-embedding",
            "AZURE_SEARCH_ENDPOINT": "https://example.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-search-key",
            "AZURE_SEARCH_INDEX_NAME": "test-index",
        },
    )
    @patch("backend.src.graph.nodes.AzureSearch")
    @patch("backend.src.graph.nodes.AzureOpenAIEmbeddings")
    @patch("backend.src.graph.nodes.AzureChatOpenAI")
    def test_audit_can_assess_ocr_when_transcript_is_missing(
        self, chat_model_class, embeddings_class, search_class
    ):
        chat_model_class.return_value.invoke.return_value = AIMessage(
            content=json.dumps(
                {
                    "status": "PASS",
                    "compliance_results": [],
                    "final_report": "No violations found.",
                }
            )
        )
        search_class.return_value.similarity_search.return_value = [
            Mock(page_content="Disclosure rules.")
        ]
        result = audit_content_node(
            {"transcript": "", "ocr_text": ["Sponsored"]}
        )
        self.assertEqual(result["final_status"], "PASS")
        query = search_class.return_value.similarity_search.call_args.args[0]
        self.assertEqual(query, "Sponsored")
        embeddings_class.assert_called_once()


if __name__ == "__main__":
    unittest.main()
