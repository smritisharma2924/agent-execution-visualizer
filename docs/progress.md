# Verification progress

## M0.4 · Repeatable baseline checks

**Local M0 exit gate:** Passed on macOS arm64 with CPython 3.12.16 and uv 0.13.9. Used a temporary local checkout of the M0.3 baseline (`1256bc1`) with the M0.4 changes and its own fresh virtual environment.

| Command or review | Observed result |
|---|---|
| `uv sync --locked --group dev` | Created the environment, resolved 83 packages, and installed 75 from the locked project and development groups. |
| `uv run python -c "from pathlib import Path; import agentlab; assert Path(agentlab.__file__).resolve() == Path('src/agentlab/__init__.py').resolve()"` | The installed package resolved to this checkout’s SDK. |
| `uv run agentlab --help` | Exited successfully and listed the config command. |
| `uv run pytest -q` | Three CLI subprocess tests passed with isolated working directories and environments. |
| `uv run ruff check .` | Passed after correcting import order in the new test module. |
| `uv run ruff format --check .` | All 15 files passed. |

Reviewed the assertions against the CLI’s JSON. Without settings, capture was false and the database path resolved to `data/traces.db`. A temporary `.env` selected its own filename and enabled capture. Conflicting exports selected the shell’s filename and disabled capture. The post-install checks ran with uv offline.

**Changed files:** `tests/integration/test_config.py`, `pyproject.toml`, `.github/workflows/checks.yml`, and `docs/progress.md`. Reviewed `AGENTS.md` against the roadmap. It already covers package boundaries, privacy defaults, preservation of execution errors, and the verification commands.

**Outstanding:** The first hosted Linux result is pending a push or pull request into main. Provider-backed check: **not run**. Review the Linux result before merging the milestone branch.

**Next step ID:** M1.1.
