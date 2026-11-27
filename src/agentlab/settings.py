"""Configuration shared by the SDK, CLI, and read API."""

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Each entry point imports the SDK at startup. Use the launch directory's
# .env, including optional provider variables, and preserve shell overrides.
load_dotenv(Path.cwd() / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    db_path: Path
    api_url: httpx.URL
    capture_payloads: bool


def get_settings() -> Settings:
    """Read the current process settings without creating any storage."""
    capture = os.environ.get("AGENTLAB_CAPTURE_PAYLOADS", "false").strip().lower()
    if capture not in {"true", "false"}:
        raise ValueError("AGENTLAB_CAPTURE_PAYLOADS must be true or false")

    db_path = os.environ.get("AGENTLAB_DB_PATH", "./data/traces.db")
    if not db_path.strip():
        raise ValueError("AGENTLAB_DB_PATH must be a file path")

    try:
        api_url = httpx.URL(os.environ.get("AGENTLAB_API_URL", "http://127.0.0.1:8000"))
    except httpx.InvalidURL:
        raise ValueError("AGENTLAB_API_URL must be an absolute HTTP(S) URL") from None
    if api_url.scheme not in {"http", "https"} or not api_url.host:
        raise ValueError("AGENTLAB_API_URL must be an absolute HTTP(S) URL")

    return Settings(
        db_path=Path(db_path).expanduser().resolve(),
        api_url=api_url,
        capture_payloads=capture == "true",
    )
