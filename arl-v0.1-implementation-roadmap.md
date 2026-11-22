# Agent Reliability Lab v0.1 implementation roadmap

Build the **Agent Execution Visualizer**, the first component of Agent Reliability Lab. A developer runs a Python agent locally, opens its saved trace, and can identify which model and tools ran, how long each operation took, where an error occurred, and what evidence is missing.

Work through one numbered step at a time. Check its result before continuing. At each milestone gate, record the commands, observed results, and next step in `docs/progress.md`. All checkboxes below describe work to verify during implementation.

| Build order | Evidence needed to advance |
|---|---|
| [Foundations](#foundations) | Shared architecture, trace schema, and interpretation rules |
| [M0](#m0-project-contract-and-setup) · 4 steps | A clean environment installs and passes baseline checks |
| [M1](#m1-independent-example-agent) · 4 steps | A generic agent executes known tools and failure cases |
| [M2](#m2-tracing-sdk) · 6 steps | Real callbacks produce a sanitized, verifiable JSON trace |
| [M3](#m3-persistence) · 6 steps | Saved starts, finishes, and failures survive restart |
| [M4](#m4-read-api) · 4 steps | Three read-only endpoints expose stored evidence |
| [M5](#m5-dashboard) · 4 steps | A developer can locate and inspect a failed step in the UI |
| [M6](#m6-integration-and-release) · 4 steps | A clean checkout runs the demo and the installed SDK works |

## Foundations

### 01 · Architecture and repository

**Write path:** Process A runs the example agent and its tracer together. LangChain callbacks feed the adapter, which translates them into framework-neutral collector operations. The collector passes sanitized records to local storage. Process A can finish before the reader starts.

**Read path:** Process C (Streamlit) requests data over HTTP from process B (FastAPI). The API reads the same SQLite file through the storage layer. Streamlit makes these requests server-side. The dashboard needs neither SQLite access nor browser CORS configuration.

**Scope.** Support saved traces on one machine, one top-level synchronous invocation per collector, and one writer process with concurrent readers. Use LangChain’s graph runtime through callbacks. Defer async invocation, distributed or multi-agent tracing, token streaming, LangGraph checkpoints, OpenTelemetry export, automatic agent discovery, and cloud hosting. The visualizer records observable execution. A separate deterministic test checks the toy task’s result. General evaluation, run comparison, and fault injection belong to later work.

**Repository map.** Scaffold the layout in M0.2. The last column identifies when each part acquires working behavior.

| Path | Responsibility | Implement |
|---|---|---|
| `pyproject.toml`, `.python-version`, `uv.lock`, `.gitignore` | Packaged Python 3.12 project, explicit build backend, console entry point, reproducible dependencies, local-file exclusions | M0 setup · M6 wheel |
| `src/agentlab/settings.py`, `.env.example` | Shared configuration, database path, API URL, and capture policy | M0 settings · M6 verify template |
| `src/agentlab/cli.py` | `agentlab` console commands for configuration, database setup, and trace management | M0 help/config · M3 management |
| `src/agentlab/tracing/` | Run/Span models, collector, timing, invocation wrapper, LangChain adapter, serializer, JSON export | M2 |
| `src/agentlab/storage/` | Storage interface, memory implementation for tests, SQLModel tables and SQLite adapter | M2 in-memory collection · M3 storage protocol and persistence |
| `src/agentlab/api/` | FastAPI app factory, read schemas and routes. Export `app` from `agentlab.api.main` | M4 |
| `examples/toy_agent/{tools,agent,run,scripted_model}.py` | Generic tools, agent builder, CLI runner, offline model double. The example imports the SDK. The SDK stays independent of the example | M1 agent · M2 tracing · M3 persistence |
| `dashboard/app.py` | HTTP client, run history, timeline, inspector | M5 |
| `tests/{unit,integration,fixtures}/` and CI configuration | Behavioral checks with isolated fixtures, offline CI, cross-component and subprocess coverage | M0 baseline · M1–M6 with each behavior |
| `docs/mvp.md`, `docs/architecture.md` | Scope, schema, policies, dependencies between layers, acceptance gates | M0.1 |
| `AGENTS.md`, `docs/progress.md` | Concise repository instructions and a record of verification and next steps | M0.4 onward |
| `docs/compatibility.md`, `docs/api.md`, `docs/screenshots/`, `README.md` | Tested versions and limits, HTTP contract, visual evidence, setup and release runbook | M0/M6 compatibility · M4 API · M5 screenshots · M6 README |

### 02 · Execution data model

One **Run** represents a complete invocation. One **Span** represents an operation within it. Every span carries the owning `run_id`. The example tree below shows why a chronological list alone cannot establish parentage.

```text
Run R1
└─ synthetic agent root
   └─ framework root chain
      ├─ model node → chat model call
      ├─ tools node → lookup_item
      └─ model node → final chat model call
```

The runtime may emit a different number of chain nodes. Preserve the observed tree. A framework callback’s `run_id` identifies one operation and maps to one span. Preserve its `parent_run_id` independently of the resolved parent. Tool-call IDs inside model messages identify requests and responses in that conversation.

| Record | Fields |
|---|---|
| **Run** | `run_id` (UUID primary key), `agent_name`, `schema_version`, `started_at`, `ended_at?`, `duration_ms?`, `status`, `trace_state`, `error_type?`, `error_message?`, `input_preview?`, `output_preview?` |
| **Span identity** | `span_id` (UUID primary key), `run_id` (foreign key), `parent_span_id?`, `framework_run_id?`, `framework_parent_run_id?`, `kind`, `name`, `sequence` |
| **Span timing and state** | `started_at`, `ended_at?`, `start_offset_ms`, `duration_ms?`, `status` |
| **Span details** | `input_data?`, `output_data?`, `error_type?`, `error_message?`, `metadata_json`, `input_tokens?`, `output_tokens?`, `total_tokens?` |

`?` marks a nullable field. Span kinds are `agent`, `chain`, `model`, and `tool`. Execution statuses are `running`, `completed`, `failed`, and `interrupted`. Trace quality is recorded separately as `complete` or `partial`.

### 03 · Rules for interpreting a trace

| Evidence | What to record or display |
|---|---|
| Invocation returns normally | Mark the run `completed`. A recovered tool error still leaves a failed tool span. Task correctness requires its own assertion. |
| Exception or observed interruption | Mark an escaping failure `failed`. On `KeyboardInterrupt`, record `interrupted` and close open spans accordingly. Preserve the original exception. |
| Start observed, finish missing | Keep `running` with null end time. Display **unfinished / liveness unknown**. Age alone establishes neither liveness nor interruption. |
| Collection, serialization, or persistence loses evidence | Mark the trace `partial` where possible and report a safe diagnostic. Preserve the agent’s result or original error. A run can be `completed` with a partial trace. |
| Timing | Use timezone-aware UTC timestamps and differences from `perf_counter_ns()` for offsets and durations. Store elapsed values. Overlapping child durations can sum to more than their parent’s duration. |
| Usage | Count reported message usage once per model span. Keep unknown values null and measured zeros zero. Label incomplete aggregate coverage **known usage only**. Leave cost unestimated. |
| Payloads and errors | Default to safe structural metadata, exception type, and a fixed safe summary. Apply the same explicit preview policy to inputs, outputs, and error text. Exclude raw stack traces, whole callback kwargs, and arbitrary object representations. Enforce M2.5 limits before any sink. |

## M0. Project contract and setup

**Objective.** Produce an installable, reproducible baseline with written decisions. **Prerequisites.** Python packages and imports, isolated environments, Git branches/diffs/commits, behavioral unit tests, JSON, type hints, and uv project basics.

### M0.1 · Specify scope and acceptance criteria

Write `docs/mvp.md` and `docs/architecture.md`. Capture the three processes, supported sync invocation, generic example, Run/Span contract, status and capture rules, deferred features, and M0–M6 gates. List open decisions with minimal proposed defaults.

- [ ] **Verify** both documents agree on dependency direction, HTTP-only dashboard access, and how execution status differs from task correctness. Resolve blocking contradictions before scaffolding.

### M0.2 · Initialize the packaged Python project

Create the repository layout above with uv, Python 3.12, an explicit build backend, `src/agentlab`, and required `__init__.py` files. Configure the `agentlab` console entry point. Commit `uv.lock`. Ignore `.env`, `.venv`, caches, local data, and trace exports.

- [ ] **Verify** `uv sync` succeeds, `uv run python -c "import agentlab"` imports the package from `src`, and `uv run agentlab --help` works. Inspect Git status for secrets or databases.

### M0.3 · Configure dependencies and shared settings

Lock compatible versions of LangChain, Pydantic 2, SQLModel, FastAPI, Uvicorn, Streamlit, Plotly, HTTPX, and python-dotenv. Put pytest and Ruff in the dev group and one provider integration in the optional `live` extra. Load `.env` at startup for the CLI, SDK, and API. Exported variables take precedence. Resolve `data/traces.db` to an absolute path from the repository working directory. Default payload capture to off.

- [ ] **Verify** `agentlab config` exposes only nonsecret settings, CLI and API resolve the same absolute path from the root, and `uv sync --locked --extra live` installs the selected integration. Record tested versions in `docs/compatibility.md`.

### M0.4 · Establish verification and repository guidance

At implementation time, write a concise `AGENTS.md` covering package boundaries, verification commands, privacy defaults, and preservation of execution errors. Have the coding tool read it explicitly. Test settings precedence and capture defaults. Configure Ruff and credential-free offline CI against `uv.lock`. Put the next step ID in `docs/progress.md`.

- [ ] **Verify** `uv run pytest -q`, `uv run ruff check .`, and `uv run ruff format --check .` pass. Inspect the assertions for the two configuration behaviors.

**Deliverables:** packaged scaffold, shared settings, lockfile, CI, initial tests, design and repository guidance.  
**Exit gate:** A clean environment installs from the lockfile, imports the package, runs CLI help, and passes configuration and quality checks. Resolve blocking scope or architecture decisions before M1.

## M1. Independent example agent

**Objective.** Demonstrate predictable tool interactions and failure cases before attaching the tracer. **Prerequisites.** Typed tool calls, `AIMessage`, `ToolMessage`, the `create_agent` loop, and injecting different models into one builder.

### M1.1 · Implement deterministic, domain-neutral tools

In `examples/toy_agent`, define typed `@tool` functions with docstrings. `lookup_item(key)` reads a fixed in-memory catalog. `add_numbers(a, b)` returns a sum without using `eval`. `fail_demo()` raises `DemoToolError`. Keep domain logic in the example and use separate fixture data in tests.

- [ ] **Verify** known and unknown keys, arithmetic, and the exact exception type directly, without a network connection, credentials, or trace database.

### M1.2 · Create the agent and command-line runner

Implement `build_agent(model)` with `langchain.agents.create_agent` and a concise system prompt. Provide `python -m examples.toy_agent.run` with modes `scripted|live` and scenarios `success|failure|slow`. Live mode reads a matching `provider:model` identifier from `AGENT_MODEL`. Invoke with a `messages` input and finite `recursion_limit`. Return the final assistant response and exit nonzero on fatal failure.

- [ ] **Verify** a live smoke run can call a tool and finish. Allow live tool order to vary. Missing credentials produce a clear setup message without exposing a key.

### M1.3 · Add a deterministic tool-calling model double

Implement `_generate`, `_llm_type`, and `bind_tools` on a test `BaseChatModel` subclass compatible with the lockfile. Return `ChatResult` containing `ChatGeneration` with `AIMessage.tool_calls` and unique tool-call IDs. Match each returned `ToolMessage` before continuing. Script lookup → addition → final answer. Use inherited `invoke` through the real agent loop so LangChain dispatches callbacks.

- [ ] **Verify** two offline success runs produce the expected tool calls and results. A binding or message-schema mismatch must surface as a failure.

### M1.4 · Create failure, pause, and outcome scenarios

Script `fail_demo()` and propagate `DemoToolError` through the runtime. Configure and document propagation if framework defaults handle it differently. Add a slow tool with a ready-to-interrupt marker and a controlled wait. Independently record actual calls and assert that looking up `alpha` returns the fixture record and `add_numbers(2, 3)` returns `5`.

- [ ] **Verify** success exits 0, failure exits nonzero with the expected type, and the slow path can be interrupted. A final answer claiming success without the required tool call fails the independent outcome assertion.

**Deliverables:** generic tools, agent builder, runner, scripted model, fixtures, and outcome tests.  
**Exit gate:** The same builder accepts scripted and live models. Scripted success, propagated failure, and interruption work independently of tracing. The outcome test detects missing or incorrect work.

## M2. Tracing SDK

**Objective.** Emit one versioned, sanitized JSON trace from a real agent invocation, using in-memory collection. **Prerequisites.** Callback lifecycle, UUIDs, parent-child trees, context managers, exception cleanup, monotonic clocks, and locks for overlapping callbacks.

### M2.1 · Define Run, Span, and collector invariants

Implement the Foundations models in Pydantic and the collector operations `start_run`, `start_span`, `finish_span`, `fail_span`, and `finish_run`. Allocate one collector, lock, and synthetic agent root per invocation. Enforce unique IDs, same-run parents, one terminal transition per span, and nullable timing for unfinished work. Keep LangChain types out of the core.

- [ ] **Verify** synthetic events cover model/tool siblings, nesting, repeated names, duplicate finishes, unknown parents, and missing starts. Check exact IDs and states. Duplicate finishes are idempotent. Missing evidence produces a diagnostic and partial trace.

### M2.2 · Implement timing and an invocation wrapper

Implement the SDK’s `trace_run` context manager to own the collector and root. Apply the timing and status rules from Foundations. Re-raise the original exception on failure or interruption. At normal return, keep any unclosed child unfinished and mark the trace partial. Expose the invocation’s handler as `trace.handler`.

- [ ] **Verify** injected clocks give exact durations and nonnegative start offsets. Exercise normal return with an open child, escaping failure, and interruption. Compare run duration with measured elapsed time.

### M2.3 · Implement the LangChain callback adapter

Subclass `langchain_core.callbacks.BaseCallbackHandler`. Match explicit positional arguments and keyword `run_id`, `parent_run_id`, and `**kwargs`. Accept missing serialized metadata.

| Operation | Start | Finish | Error |
|---|---|---|---|
| Chat model | `on_chat_model_start` | `on_llm_end` | `on_llm_error` |
| Tool | `on_tool_start` | `on_tool_end` | `on_tool_error` |
| Chain | `on_chain_start` | `on_chain_end` | `on_chain_error` |

Pass `[trace.handler]` through `invoke`’s `config["callbacks"]` alongside the finite recursion limit (the source example uses 25). Reserve `on_llm_start` for future non-chat support.

- [ ] **Verify** a scripted `create_agent` run emits real model, tool, and chain events. Assert the expected operations while allowing the internal chain-node count to vary.

### M2.4 · Resolve hierarchy and identity safely

Map each callback run ID to one span ID. Persist every observed chain as `kind=chain`, with its framework root beneath the synthetic root. Preserve raw framework parent IDs and resolve late parents. If a parent never arrives, leave `parent_span_id` null, mark the trace partial, and expose an unresolved-parent diagnostic for grouping under the UI root. Use observed IDs to establish parentage.

- [ ] **Verify** nesting, two calls with the same name, overlapping calls, late parents, and a missing parent. No cycles, cross-run parent links, or duplicate spans per callback operation.

### M2.5 · Normalize payloads, errors, and token usage

Apply one serializer before every sink. For opt-in previews, allowlist fields, recursively redact secret keys, bound each encoded JSON payload to **4 KiB** and nesting depth to **5**, and represent unknown objects by type only. For supported chat results, read `generation.message.usage_metadata` once per model span. Preserve nulls and avoid double counting provider metadata.

- [ ] **Verify** nested `authorization`, `api_key`, and `password` fields, a secret-bearing exception, oversized text, unknown objects, missing usage, and reported zero usage. Search emitted JSON for the seeded secrets.

### M2.6 · Integrate and validate JSON tracing

Wrap the example invocation with `trace_run`. Add `--trace-json PATH` to export a versioned envelope containing the run and its spans, including after a caught invocation failure. Preserve the CLI failure exit code. Add a recovered-error adapter fixture and a broken-sink test.

- [ ] **Verify** success, failure, and interruption exports reopen and validate against the schema. Confirm expected model/tool spans, a failed `DemoToolError` tool, and explicit interruption. The recovery fixture must show a failed tool within a completed run. The broken sink must warn safely and preserve the original result or exception. Account for every orphan and missing finish.

**Deliverables:** models, collector, wrapper, adapter, serializer, JSON export, and focused tests.  
**Exit gate:** A supported invocation emits schema-valid, sanitized JSON with distinct IDs, observed parents, correct statuses and timings. Unknown usage and lost evidence remain visible. Observer faults preserve execution behavior.

## M3. Persistence

**Objective.** Preserve starts and finishes as they occur so another process can inspect a trace after the writer exits. **Prerequisites.** Primary and foreign keys, transactions, SQLModel sessions, indexes, SQLite write-ahead logging (WAL), and schema versions.

### M3.1 · Introduce the storage protocol

Define `TraceStore` with `create_run`, `upsert_span`, `finalize_run`, `list_runs`, `get_run`, and `delete_run`. Retain `MemoryStore` for tests and add a separate `SQLiteStore`. Send sanitized records directly from the collector, persist starts immediately, serialize mutations using its lock, and bound writes. Surface failures through safe diagnostics.

- [ ] **Verify** the contract first in memory and against a temporary SQLite store as the schema lands in M3.2. Repeated span upserts keep one row. Repeated finalization preserves an established terminal state.

### M3.2 · Create the SQLite schema and initializer

Map runs and spans to SQLModel tables. Enforce the `run_id` foreign key and same-run parent references, allowing null parents until resolved. Index `runs(started_at, run_id)`, `runs(status)`, and `spans(run_id, sequence)`. Enable `foreign_keys` on every connection, WAL, and a finite busy timeout. Use a short-lived session per operation or API request, even with `check_same_thread=False`.

Implement `agentlab db init` with a `PRAGMA user_version` check. Report the resolved database path and version in safe diagnostics. Keep API schemas separate from database models.

- [ ] **Verify** repeated initialization is safe, invalid run references fail, and an incompatible schema produces an actionable error while preserving existing data.

### M3.3 · Persist lifecycle transitions atomically

Connect `SQLiteStore` to `trace_run`. Commit the run and synthetic root before invocation. Commit each span start before its callback returns. Update the same row on completion or error, using short transactions. Finalize the run and root together. Resolve deferred parent links while retaining the raw IDs. If storage fails, retain the partial trace in memory, emit one safe warning, and attempt to persist `trace_state=partial` if storage recovers.

- [ ] **Verify** a second connection sees the run and slow tool as `running` during execution. On completion the same IDs have end times and durations. Inject a write fault and check that the original result or exception survives.

### M3.4 · Prove restart, interruption, and crash behavior

Run the slow scenario in a child process against a temporary database. Emit its marker **after the tool start commits**. In separate runs, trigger a cooperative `KeyboardInterrupt` and force-terminate the child without cleanup. Reopen each file in a fresh process. Provide an explicit CLI `mark-interrupted RUN_ID` action for a user who confirms the writer has stopped. API startup must leave stored statuses intact.

- [ ] **Verify** cooperative interruption records `interrupted` with known timing. After a force-kill, the open run and tool retain `running` and null end times. Earlier finished spans survive unchanged. The display meaning is **unfinished / liveness unknown**.

### M3.5 · Implement stable queries and local trace management

Implement filtered, paginated `list_runs` ordered by `started_at` descending, then `run_id`. Return every span from `get_run`, ordered by `sequence`, then `span_id`. Parameterize operations. Expose the resolved database path in CLI help/config diagnostics.

| Command | Behavior |
|---|---|
| `agentlab traces list` | List saved runs |
| `agentlab traces show RUN_ID` | Retrieve one run and its spans |
| `agentlab traces export RUN_ID --output PATH` | Write sanitized, schema-valid JSON |
| `agentlab traces delete RUN_ID --yes` | Delete only that run and its spans in one transaction |

- [ ] **Verify** the same run matches before and after restart, pages are stable for unchanged data, and an unknown ID produces a clear missing-record result. Validate the export against the M2 schema. Delete one run and confirm the others remain.

### M3.6 · Verify isolation and persistence guarantees

Use a separate temporary file per test. Exercise repeated writes, open spans, concurrent API-style reads, locked/unwritable storage, and opt-in payloads containing seeded secrets. Document one local writer and concurrent readers. If all writes fail, report it on the console and make the available in-memory trace exportable.

- [ ] **Verify** storage and collector tests pass together. Search database fields and exports for seeded secrets. Forced write failures produce a visible diagnostic and cannot appear as a complete trace.

**Deliverables:** storage protocol, SQLite adapter and schema initializer, management CLI, persistence tests, and restart evidence.  
**Exit gate:** Completed, failed, interrupted, and unfinished traces survive reopening with the expected evidence. Starts are durable, reads are stable, deletion is scoped, and storage-failure and redaction checks pass.

## M4. Read API

**Objective.** Let a client read saved traces through three schema-validated HTTP endpoints. **Prerequisites.** HTTP GET, JSON response schemas, pagination, status codes, dependency injection, and FastAPI testing.

### M4.1 · Build the application factory and read schemas

Create `create_app(settings)` and export `app` from `agentlab.api.main`. Inject storage with short-lived sessions. Define Pydantic `RunSummary`, `RunDetail`, `SpanRead`, `RunsPage`, and `HealthResponse`, preserving nulls, UTC timestamps, and enums. Check database existence and schema compatibility without creating or migrating it at startup. Bind the documented server to `127.0.0.1`.

- [ ] **Verify** tests can inject a temporary database. Missing/incompatible storage yields a readable setup or health failure. Importing the app leaves database contents intact.

### M4.2 · Implement health and paginated run history

- **`GET /health`** checks readable, compatible storage. Return 200 with `status=ok` and `schema_version`, or 503 with a safe diagnostic.
- **`GET /runs`** accepts `limit` (default 20, range 1–100), `offset` (default 0, nonnegative), and an optional valid `status`. Return summaries in storage order with `items`, `limit`, `offset`, and the total matching count. Use only sanitized previews.

- [ ] **Verify** an empty database returns `items=[]` and `total=0`. A failed-status filter returns only failed runs. Unknown statuses, negative offsets, and excessive limits return 422. Responses exclude ORM internals.

### M4.3 · Implement run details and safe errors

**`GET /runs/{run_id}`** takes a UUID and returns `{run: RunDetail, spans: list[SpanRead]}`. Preserve raw parent IDs, sequence, trace quality, nullable usage, and unfinished spans. Return 404 for an unknown UUID, 422 for a malformed ID, and a safe 503 for a storage read failure. Exclude raw exceptions and credentials. Execution and deletion stay outside the HTTP API.

- [ ] **Verify** a known failed run’s span IDs and statuses match storage exactly. An open span remains unfinished. OpenAPI documents the three GET routes.

### M4.4 · Test the contract and run a local API smoke check

Use FastAPI `TestClient` and temporary storage to test health, success, failure, interruption, unfinished work, filtering, pagination, unknown IDs, and unavailable storage. Document envelopes and errors in `docs/api.md`. Start Uvicorn and use `curl` against an actual example trace.

- [ ] **Verify** `uv run pytest tests/integration -q` passes offline. Check `/health`, find the example in `/runs`, compare its detail span IDs to `agentlab traces show RUN_ID`, and inspect the contract at `/docs`.

**Deliverables:** FastAPI app, read schemas, API tests, and API documentation.  
**Exit gate:** All three endpoints serve schema-valid results. Empty, malformed, missing, failed, partial, and unfinished cases behave as documented, and a real saved trace is retrievable over HTTP.

## M5. Dashboard

**Objective.** Use two views, history and execution details, to understand a saved run without consulting logs. **Prerequisites.** Streamlit reruns/session state, HTTP timeouts, parent traversal, and elapsed-time timelines.

### M5.1 · Build the API client and history view

Use HTTPX with `AGENTLAB_API_URL`, explicit timeouts, and response validation. Show status, start time, agent name, elapsed time, trace quality, and run ID. Add pagination, status filtering, and refresh. Store `selected_run_id` in session state. Handle empty data, malformed responses, an unreachable API, and a selected run deleted since loading.

- [ ] **Verify** selection from seeded history, a helpful error and retry path with the API stopped, and recovery on refresh. Check that dashboard modules access traces only over HTTP.

### M5.2 · Render hierarchy and elapsed-time bars

Traverse parents deterministically, detect cycles, and group unresolved parents. Render an indented tree and horizontal Plotly bars keyed by `span_id`. Show model/tool rows by default. **Show runtime spans** reveals chain/root rows. When collapsing rows, walk up to the nearest visible ancestor for display. Position bars using `start_offset_ms` and `duration_ms`. Provide a synchronized span selector so inspection works independently of chart clicks.

- [ ] **Verify** duplicate names remain independently selectable. Nested and overlapping operations retain the correct hierarchy and timing. Use explicit units and an open marker for unfinished spans with unknown duration.

### M5.3 · Implement the inspector and honest metrics

Show span kind, name, IDs, observed parent, status, timestamps, duration, safe error summary, allowed payloads, and usage. Indicate when capture is disabled. Display run duration, model/tool counts, and known token usage with coverage. Use explicit labels for completed, failed, interrupted, unfinished/liveness unknown, and partial traces. Pair status color with words and icons or shapes.

- [ ] **Verify** a failed step can be diagnosed from the inspector. A completed run can visibly contain a failed tool. Missing usage reads **unavailable** and partial coverage reads **known usage only**. Execution labels make no claim about task correctness.

### M5.4 · Validate interaction and visual behavior

Create API fixtures for empty history, long/duplicate names, deep trees, unresolved parents, partial traces, missing usage, and unfinished spans. Test pure tree and metric functions and a Streamlit smoke path where practical. At laptop width, navigate history → select → inspect → refresh → back. Save success, failure, and unfinished screenshots in `docs/screenshots/` and results in `docs/progress.md`.

- [ ] **Verify** text wraps clear of controls, statuses are readable without color, every listed span is selectable, refresh never mixes selections, and the UI recovers from timeouts.

**Deliverables:** HTTP client, history view, tree/timeline, step inspector, presentation tests, and screenshots.  
**Exit gate:** From the dashboard alone, explain any demo run’s supported model/tool sequence, durations, failure location, and trace limitations. Missing-data and API-failure checks pass.

## M6. Integration and release

**Objective.** Verify the complete evidence path, installable SDK, and documented demonstration from a fresh checkout. **Prerequisites.** Integration and subprocess tests, wheels, smoke tests, regressions, and Git release tags.

### M6.1 · Exercise the end-to-end and failure matrix

Run the offline sequence through real components: scripted `create_agent` invocation → callback collector → temporary SQLite → FastAPI detail response. Compare operations, IDs, parents, durations, sanitized fields, and failures with the known execution. Include recovered tool error via the deterministic adapter fixture, storage failure, repeated names, unknown usage, interruption, and force-kill. Run the independent M1 outcome test.

- [ ] **Verify** the [release evidence checklist](#release-evidence-checklist) against observed results as each release check becomes available. Confirm a false claim fails the outcome assertion even when the run completes.

### M6.2 · Measure observer overhead and document support

Choose and justify a local overhead budget **before measuring**. Warm up and run the same scripted scenario at least 30 times per mode with tracing off, in memory, and in SQLite. Report median and p95 elapsed times and absolute deltas against tracing off. Record the machine, locked versions, span count, and payload policy. Document sync invocation, single-writer support, and absent heartbeat/live updates in the README and `docs/compatibility.md`.

- [ ] **Verify** the benchmark is reproducible and meets its budget. Investigate overruns before release. Separately run a provider-backed success with an observed tool interaction on the locked versions. Save sanitized evidence and keep offline CI credential-free. If live access is unavailable, record that check as **not run** and limit the compatibility claim accordingly.

### M6.3 · Verify local installation and command contracts

Set version `0.1.0`, build with `uv build`, and install the wheel in a clean temporary environment outside the checkout. Package `src/agentlab` and its CLI. Document the example and dashboard as checkout entry points.

- [ ] **Verify** `import agentlab`, `agentlab --help`, database initialization, and a small installed-SDK trace from outside the repository. Run help examples, check tested dependencies against the lockfile, and inspect the distribution for secrets, databases, and exports.

### M6.4 · Run the fresh-checkout demonstration and release

Write the README and `.env.example` using the [launch runbook](#launch-runbook). Include scenario commands, privacy defaults, trace management, and troubleshooting. Follow the README from a fresh checkout. Run the full offline suite and Ruff, review the final diff, and record evidence in `docs/progress.md`. Commit the verified release and tag `v0.1.0`. Registry publication is outside the release scope.

- [ ] **Verify** the fresh checkout installs, initializes, records success and failure, serves both through the API and dashboard, identifies the failed tool, and retains the same IDs after restart. Document the live result or its explicit not-run limitation.

**Deliverables:** installable wheel, README, lockfile, compatibility and benchmark notes, screenshots, verification log, and release tag.  
**Exit gate:** Mandatory offline checks, overhead budget, wheel installation, and clean-checkout demo pass. The dashboard explains saved traces, any live-support claim has evidence, and no known correctness or data-leak blocker remains.

## Launch runbook

Use this procedure in M6 to verify the finished checkout. Run all commands from the same repository root in a macOS/Linux shell with Git and uv installed. These are the project’s intended command contracts.

**1. Prepare the checkout.** Use the pinned Python version and locked dependencies.

```sh
uv sync --locked
cp .env.example .env
uv run agentlab config
uv run agentlab db init
uv run pytest -q
```

Confirm the template values and resolved absolute database path.

```dotenv
AGENTLAB_DB_PATH=./data/traces.db
AGENTLAB_API_URL=http://127.0.0.1:8000
AGENTLAB_CAPTURE_PAYLOADS=false
```

**2. Record an offline success in terminal A.** Expect exit 0, the final response, and a run ID. Find that ID in the list. The writer can run before the API starts.

```sh
uv run python -m examples.toy_agent.run --mode scripted --scenario success
uv run agentlab traces list
```

**3. Start the API in terminal B.** Check [health](http://127.0.0.1:8000/health) and the [interactive API reference](http://127.0.0.1:8000/docs).

```sh
uv run uvicorn agentlab.api.main:app --host 127.0.0.1 --port 8000
```

**4. Start Streamlit in terminal C.** Open the [local dashboard](http://127.0.0.1:8501), select the saved run, and inspect a model or tool span.

```sh
uv run --env-file .env streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

**5. Demonstrate failure, interruption, and persistence.** Run these commands individually in terminal A.

```sh
uv run python -m examples.toy_agent.run --mode scripted --scenario failure
uv run python -m examples.toy_agent.run --mode scripted --scenario slow
```

The first command exits nonzero and saves the failed tool. For the slow run, wait for the committed-start marker, press Ctrl-C, refresh, and inspect the interrupted run. The separate M3 force-kill test covers unfinished work. Restart the API and UI and check the same saved IDs. For sanitized export or scoped deletion, use the commands in M3.5 with an actual run UUID.

**6. Check the live integration when available.** In `.env`, set `AGENT_MODEL` to a valid `provider:model` for the integration chosen in M0, and set its required API-key variable. Keep the key out of Git. Live calls may incur provider charges.

```sh
uv sync --locked --extra live
uv run --extra live python -m examples.toy_agent.run --mode live --scenario success
```

Confirm at least one real model span and tool interaction. If the model skips tools, refine the demo request and repeat. Tool order and reported usage can vary by provider.

| Symptom | Check |
|---|---|
| No runs visible | Compare absolute database paths from `agentlab config`, check filters, and refresh. |
| API unreachable or 503 | Inspect `/health`, initialization, schema version, path permissions, and port 8000. |
| SQLite locked | Check for unintended writers and the busy timeout. Keep WAL files with the database. |
| Hidden payloads or missing usage | Check the capture setting and whether the provider supplied usage. |

## Release evidence checklist

Record the command, observed result, and relevant commit for each row in `docs/progress.md`.

- [ ] **Success and propagated failure (M1, M2, M6).** JSON and API match observed model/tool calls. A tool exception yields a failed span with a safe error type. An escaping error also yields a failed run and nonzero exit.
- [ ] **Recovery and task outcome (M1, M2, M6).** The recovery fixture retains a failed tool in a completed run. Separate assertions validate the toy tool results and reject an unsupported final claim.
- [ ] **Identity and timing (M2, M5).** Repeated names have distinct IDs. Nested and overlapping calls retain parents. Unresolved parents are visible. Injected clocks yield exact elapsed times.
- [ ] **Usage and privacy (M2–M4).** Known usage is counted once, missing usage stays null, and capture defaults off. Seeded secrets are absent from JSON, database fields, API responses, and diagnostics.
- [ ] **Interruption and loss of storage (M2, M3).** Ctrl-C records interruption. Force-kill retains durable starts and completed spans. A failed write warns safely, preserves recoverable partial evidence, and leaves the original result or error intact.
- [ ] **API contract (M4).** Validate 200, 404, 422, and 503 responses, pagination, filters, and empty/unfinished results.
- [ ] **Dashboard (M5).** Select, inspect, and refresh a trace. Identify failure and missing data from the UI alone.
- [ ] **Release (M6).** Reproduce the benchmark, wheel installation, and README demo. Retain a sanitized live smoke result for any live-compatibility claim.

## Technical references

- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents) — create_agent, messages input, and model/tool loop.
- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools) — Typed tools, schemas, and tool behavior.
- [LangChain callback reference](https://reference.langchain.com/python/langchain-core/callbacks/base/BaseCallbackHandler) — BaseCallbackHandler and lifecycle methods.
- [on_chat_model_start](https://reference.langchain.com/python/langchain-core/callbacks/base/CallbackManagerMixin/on_chat_model_start) — Explicit start signature; run_id and parent_run_id.
- [on_llm_end](https://reference.langchain.com/python/langchain-core/callbacks/base/LLMManagerMixin/on_llm_end) — Chat/model completion carries LLMResult.
- [UsageMetadata](https://reference.langchain.com/python/langchain-core/messages/ai/UsageMetadata) — Standard input, output, and total token fields.
- [Python time](https://docs.python.org/3/library/time.html) — Monotonic clocks and perf_counter_ns.
- [uv projects](https://docs.astral.sh/uv/guides/projects/) — Install link, environments, lockfiles, run, and build.
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) — TestClient and HTTP-level assertions.
- [SQLModel sessions](https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/) — Request-scoped sessions with dependencies.
- [Streamlit Plotly charts](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart) — Render interactive timeline charts.
- [SQLite write-ahead logging](https://www.sqlite.org/wal.html) — Concurrency and operational behavior of WAL.
- [OpenAI: prompts and repository instructions](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) — Keep context specific, concise, and useful.
- [RunnableConfig](https://reference.langchain.com/python/langchain-core/runnables/config/RunnableConfig) — Invocation callbacks and recursion_limit.

## Working with Codex across sessions

| Suggested sessions | Work through in order |
|---|---|
| 01–02 · M0 | Write the contract and scaffold. Establish configuration and baseline checks. |
| 03–04 · M1 | Build tools and runner. Exercise scripted scenarios and outcome assertions. |
| 05–08 · M2 | Models and timing → callbacks and parents → sanitization → JSON integration. |
| 09–12 · M3 | Schema and store → lifecycle writes → crash tests → queries and CLI. |
| 13–14 · M4 | Read schemas and endpoints → HTTP verification against saved traces. |
| 15–17 · M5 | History → tree and timeline → inspector and visual checks. |
| 18–20 · M6 | Integration and overhead → packaging → clean-checkout release. |

Use the session ranges for pacing. Keep the numbered implementation steps and their gates in order even when a check needs another session.

1. **Orient.** Inspect the current branch, Git status, and last verified step. Read the applicable `AGENTS.md`, `docs/mvp.md`, `docs/architecture.md`, and `docs/progress.md` as they become available. At the first session, start from Foundations and M0.1.
2. **Scope and implement.** Select the next numbered step. Identify its contract, smallest change, affected components, and verification. Implement that step, preserving unrelated edits. One or two verified steps fit a typical focused session.
3. **Verify and repair.** Run the step checks and inspect actual output and the diff. During a separate review pass, check status transitions, parent IDs, exception propagation, data capture, and scope. Reproduce failures before fixing them and keep assertions meaningful. Personally run the applicable demo.
4. **Commit.** Use a short branch per milestone, for example `m2/tracing-sdk`. Review `git diff`, run the applicable checks, and commit each verified logical change with a descriptive message. Commit `uv.lock` with dependency changes. Keep credentials, local databases, and trace exports out of Git. Merge into a working main branch once the milestone gate passes.
5. **Hand off.** Record completed IDs, files changed, commands and observed results, relevant commit, limitations, and the exact next step in `docs/progress.md`. Resume from this record in a fresh chat at a milestone boundary or when context becomes unclear.

**Reference for M0.4.** The durable repository guidance belongs in `AGENTS.md`: component boundaries from Foundations, commands from M0.4, capture policy from M2.5, and the rule that tracing preserves the agent’s result or original error. Session-specific evidence belongs in `docs/progress.md`.
