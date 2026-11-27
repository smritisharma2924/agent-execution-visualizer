# M0.3 dependency and settings checks

The locked environment was installed on macOS arm64 with CPython 3.12.16 and uv 0.13.9. Run the following from the checkout root to install the optional OpenAI integration and check the configuration.

```sh
uv sync --locked --extra live
uv run --locked --extra live agentlab config
uv run --locked --extra live python -c "from agentlab.api import get_settings; print(get_settings().db_path)"
uv run --locked --extra live python -c "from langchain_openai import ChatOpenAI; print(ChatOpenAI.__name__)"
```

The CLI, SDK, and API settings entry point read the launch directory’s `.env` at startup. Shell exports take precedence. Relative database paths resolve from the working directory. With the defaults, the API prints the same absolute path ending in `data/traces.db` as the CLI. Capture defaults to `false`; set `AGENTLAB_CAPTURE_PAYLOADS=true` to opt in. The config command shows only the database path, API origin (scheme, host, and port), and capture setting. URL credentials, paths, query strings, and fragments are omitted from that display.

## Installed versions

| Group | Distribution | Version |
|---|---|---|
| Runtime | langchain | 1.5.2 |
| Runtime | pydantic | 2.14.4 |
| Runtime | sqlmodel | 0.0.50 |
| Runtime | fastapi | 0.165.0 |
| Runtime | uvicorn | 0.54.0 |
| Runtime | streamlit | 1.67.0 |
| Runtime | plotly | 7.1.0 |
| Runtime | httpx | 0.28.1 |
| Runtime | python-dotenv | 1.2.4 |
| Development | pytest | 9.2.0 |
| Development | ruff | 0.17.6 |
| Optional `live` | langchain-openai | 1.8.5 |

The locked sync, installed dependency consistency check, and runtime import checks passed. The OpenAI integration imported without credentials. Provider-backed model invocation was **not run**. The M1 example will exercise the agent loop.
