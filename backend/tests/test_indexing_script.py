import unittest
from unittest.mock import patch

from backend.src.config import ConfigurationError
from backend.scripts.index_documents import index_docs


class DocumentIndexingScriptTests(unittest.TestCase):
    def test_missing_configuration_returns_failure(self):
        with patch(
            "backend.scripts.index_documents.get_required_environment",
            side_effect=ConfigurationError("Missing required configuration."),
        ):
            self.assertEqual(index_docs(), 1)


if __name__ == "__main__":
    unittest.main()
