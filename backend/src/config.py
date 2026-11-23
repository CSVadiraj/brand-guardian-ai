import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is missing."""


def load_project_environment() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not (PROJECT_ROOT / "pyproject.toml").is_file():
        env_path = Path.cwd() / ".env"
    load_dotenv(env_path, override=False)


def get_required_environment(*names: str) -> dict[str, str]:
    values = {name: os.getenv(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    return {name: value for name, value in values.items() if value is not None}
