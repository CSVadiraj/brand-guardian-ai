import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.src.config import (
    ConfigurationError,
    PROJECT_ROOT,
    get_required_environment,
    load_project_environment,
)


class ConfigurationTests(unittest.TestCase):
    def test_dotenv_loader_uses_repository_root_not_tests_directory(self):
        with patch("backend.src.config.load_dotenv") as load_dotenv:
            load_project_environment()
        load_dotenv.assert_called_once_with(
            PROJECT_ROOT / ".env",
            override=False,
        )
        self.assertNotEqual(
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / "backend" / "tests" / ".env",
        )

    def test_missing_configuration_lists_names_without_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError) as error:
                get_required_environment("REQUIRED_ALPHA", "REQUIRED_BETA")
        self.assertIn("REQUIRED_ALPHA", str(error.exception))
        self.assertIn("REQUIRED_BETA", str(error.exception))


if __name__ == "__main__":
    unittest.main()
