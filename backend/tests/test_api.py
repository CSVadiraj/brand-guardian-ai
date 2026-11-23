import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.src.api.server import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_audit_rejects_non_youtube_urls(self):
        response = self.client.post(
            "/audit", json={"video_url": "https://example.com/video"}
        )
        self.assertEqual(response.status_code, 422)

    def test_audit_rejects_http_urls_and_unknown_request_fields(self):
        for request_body in (
            {"video_url": "http://youtu.be/example"},
            {"video_url": "https://youtu.be"},
            {"video_url": "https://user@youtu.be/example"},
            {"video_url": "https://youtu.be/example", "unexpected": True},
        ):
            with self.subTest(request_body=request_body):
                response = self.client.post("/audit", json=request_body)
                self.assertEqual(response.status_code, 422)

    def test_audit_returns_graph_results_and_errors(self):
        graph_result = {
            "video_id": "vid-test",
            "final_status": "FAIL",
            "final_report": "Processing failed.",
            "compliance_results": [],
            "errors": ["Video processing unavailable."],
        }
        with patch("backend.src.api.server.compliance_graph.invoke", return_value=graph_result):
            response = self.client.post(
                "/audit", json={"video_url": "https://youtu.be/example"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_id"], "vid-test")
        self.assertEqual(response.json()["errors"], ["Video processing unavailable."])

    def test_openapi_documents_audit_request(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        operation = response.json()["paths"]["/audit"]["post"]
        self.assertIn("requestBody", operation)
        self.assertIn("200", operation["responses"])

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
