"""Exercise settings through the installed CLI in isolated working directories."""

import json
import subprocess
import sys
from pathlib import Path


def read_config(directory: Path, **exports: str) -> dict:
    cli = Path(sys.executable).with_name("agentlab")
    result = subprocess.run(
        [cli, "config"],
        cwd=directory,
        env=exports,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_defaults_without_dotenv_or_exports(tmp_path):
    settings = read_config(tmp_path)

    assert settings["capture_payloads"] is False
    assert settings["db_path"] == str(tmp_path.resolve() / "data" / "traces.db")


def test_dotenv_selects_database_and_enables_capture(tmp_path):
    (tmp_path / ".env").write_text(
        "AGENTLAB_DB_PATH=from-file.db\nAGENTLAB_CAPTURE_PAYLOADS=true\n"
    )

    settings = read_config(tmp_path)

    assert settings["capture_payloads"] is True
    assert settings["db_path"] == str(tmp_path.resolve() / "from-file.db")


def test_exports_override_conflicting_dotenv_settings(tmp_path):
    (tmp_path / ".env").write_text(
        "AGENTLAB_DB_PATH=from-file.db\nAGENTLAB_CAPTURE_PAYLOADS=true\n"
    )

    settings = read_config(
        tmp_path, AGENTLAB_DB_PATH="from-shell.db", AGENTLAB_CAPTURE_PAYLOADS="false"
    )

    assert settings["capture_payloads"] is False
    assert settings["db_path"] == str(tmp_path.resolve() / "from-shell.db")
