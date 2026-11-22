# Local trace architecture

## Processes and dependency direction

| Process | Owns | Boundary |
|---|---|---|
| A · Agent and tracer | One collector, lock, and synthetic agent root per synchronous top-level invocation. The example supplies the callback handler to LangChain’s agent loop. | The example imports the SDK. Only the adapter translates LangChain callback types. The framework-neutral collector submits sanitized Run and Span records to the storage interface. |
| B · FastAPI | A loopback, read-only HTTP API. `GET /health` checks storage, `GET /runs` lists saved runs, and `GET /runs/{run_id}` returns the run and its spans. | Reads the same SQLite file through storage with short-lived sessions. The API checks schema compatibility and leaves initialization and trace management to the local CLI. |
| C · Streamlit | Run history, elapsed-time timeline, and span inspector. | The Streamlit server fetches data exclusively over HTTP from process B. Only A and B need the database path. The browser communicates with Streamlit. |

`examples/toy_agent/` owns the tools, agent builder, runner, and scripted model. The independent outcome test uses separate fixture data under `tests/`. The SDK in `src/agentlab/` can be installed and used without the example. Its tracing core depends on the storage contract. The memory and SQLite implementations satisfy that contract. API response schemas are separate from database tables.

The normal deployment uses one local writer and concurrent readers. Process A may finish before either reader starts. Both the writer and API resolve the same configured database path (default `./data/traces.db` from the repository root). The dashboard uses `AGENTLAB_API_URL`, defaulting to `http://127.0.0.1:8000`.

## Run and Span contract

A Run identifies one invocation. A Span identifies one operation in that invocation. The versioned JSON export contains the run and its spans. A trailing `?` below denotes a nullable field.

| Record | Fields |
|---|---|
| Run identity | `run_id` (UUID primary key), `agent_name`, `schema_version` |
| Run lifecycle | `started_at`, `ended_at?`, `duration_ms?`, `status`, `trace_state` |
| Run detail | `error_type?`, `error_message?`, `input_preview?`, `output_preview?` |
| Span identity | `span_id` (UUID primary key), `run_id` (owning run), `parent_span_id?`, `framework_run_id?`, `framework_parent_run_id?`, `kind`, `name`, `sequence` |
| Span lifecycle | `started_at`, `ended_at?`, `start_offset_ms`, `duration_ms?`, `status` |
| Span detail | `input_data?`, `output_data?`, `error_type?`, `error_message?`, `metadata_json`, `input_tokens?`, `output_tokens?`, `total_tokens?` |

Span kinds are `agent`, `chain`, `model`, and `tool`. The wrapper creates the synthetic agent root. The adapter places the observed framework root beneath it and preserves each observed chain. Each callback operation’s `run_id` maps to one span. The adapter retains its raw `parent_run_id` and uses that ID to resolve the same-run parent, even if the parent arrives later. An unresolved parent leaves `parent_span_id` null, produces a safe diagnostic, and marks the trace partial. The dashboard groups unresolved spans visibly.

Names may repeat and children may overlap. Link operations by callback identity. Model-message tool-call IDs correlate requests with tool responses within the conversation. Reject cycles and cross-run parents. Repeated finish notifications preserve the first terminal transition. Use `sequence` and then `span_id` for stable span ordering.

## Lifecycle and evidence

| Observation | Record and interpretation |
|---|---|
| Start | Create the record as `running` with null end time and duration. Use timezone-aware UTC for timestamps and differences from `perf_counter_ns()` for offsets from run start and elapsed durations. Overlapping children can sum to more than the parent duration. |
| Normal return | Complete the run and synthetic root. A failed tool span stays `failed` after recovery. Any child lacking a finish stays open and makes the trace partial. Verify task correctness separately by asserting actual tool calls and results in the example’s outcome test. |
| Escaping exception | Record the run as `failed`, store safe error details, and re-raise the original exception. |
| Observed interruption | On `KeyboardInterrupt`, record the run and still-open spans as `interrupted` with observed timing and re-raise the interruption. |
| Writer disappears | Persisted starts without finishes retain `running` and null end time and duration. Display **unfinished / liveness unknown**. Neither elapsed wall time nor an API restart establishes a terminal state. |
| Observer loses evidence | `trace_state` describes evidence quality (`complete` or `partial`) independently of execution status. On collection, serialization, or storage loss, issue a safe diagnostic, retain available evidence in memory, and mark the trace partial wherever possible. Return the agent’s original result or re-raise its original exception. |

## Capture boundary

Use one serializer before any storage or export sink, including the memory store. With `AGENTLAB_CAPTURE_PAYLOADS=false` (the default), retain safe structural metadata, exception type, and a fixed safe error summary. Apply the same preview policy to inputs, outputs, and error text.

With capture enabled, include only explicitly allowlisted fields. Recursively redact sensitive keys such as `authorization`, `api_key`, and `password`. Limit each encoded JSON payload to **4 KiB** and nesting depth **5**. Represent unknown objects by type only. Exclude raw stack traces, whole callback kwargs, and arbitrary object representations. Diagnostics must be safe even when an exception contains a secret. Keep credentials, SQLite files, and trace exports out of Git.

Read reported `generation.message.usage_metadata` once per model span. Retain measured zero as zero and unreported values as null. Display missing usage as **unavailable** and aggregates with incomplete coverage as **known usage only**. Leave cost unestimated.

## Durable writes and independent reads

Commit the run and synthetic root together before invoking the agent. Commit each span start before its callback returns. Update the same row on finish. Finalize run and root together. Serialize mutations under the collector lock and use short transactions, foreign keys, WAL, and a finite SQLite busy timeout. If a write fails, warn safely, retain an exportable partial trace in memory, and attempt to persist its partial state when storage recovers.

FastAPI reads compatible, initialized storage without changing recorded statuses. Streamlit refreshes history or detail over HTTP and uses span IDs for selection. Hiding chain rows in the dashboard changes presentation only. The stored tree retains the observed parent links.

See the [MVP scope, milestone gates, and decisions for review](mvp.md) and the [implementation roadmap](../arl-v0.1-implementation-roadmap.md).
