# Agent Execution Visualizer v0.1

A developer can run a local Python agent, let the process exit, then open its saved trace and identify the model and tools that ran, how long each call took, and which operation failed. The dashboard must also show where evidence is missing.

## Supported workflow

1. **Record.** Process A runs the agent and tracer together. Each collector observes one top-level synchronous invocation. The generic example in `examples/toy_agent/` imports the SDK. The SDK’s LangChain adapter translates callbacks into operations for the framework-neutral collector. The collector writes sanitized records through the storage interface to local SQLite.
2. **Retrieve.** Process B runs FastAPI on loopback. It reads the same database through the storage interface and serves saved run history and details. The supported deployment is one machine with one writer and concurrent readers.
3. **Inspect.** Process C runs Streamlit. Its server gets traces exclusively through the read-only HTTP API. A developer selects a run, follows the model and tool calls in the timeline, and inspects a span by ID. Repeated calls with the same name remain individually selectable.

The SDK works independently of the example. The example uses one agent builder for a deterministic, credential-free scripted chat model and an optional live model. The scripted scenarios exercise a catalog lookup and addition, a propagated tool failure, and a slow tool that can be interrupted.

## What the trace can establish

| Question | Evidence the developer should see |
|---|---|
| Did the invocation return? | A normal return gives the run status `completed`. If the agent recovered from a tool error, that tool span still reads `failed`. An escaping exception gives the run status `failed`. |
| Did the example do the requested work? | A separate outcome test observes the actual calls and checks the fixture record for `lookup_item("alpha")` and the result `5` for `add_numbers(2, 3)`. A final answer claiming success without the required calls fails this test, even in a completed run. |
| Did the operation finish? | An observed Ctrl-C records `interrupted`. A saved start with no observed finish retains null end time and duration. The UI labels it **unfinished / liveness unknown**. |
| How much evidence is available? | A known collection or storage loss produces a safe diagnostic and a `partial` trace where possible. Unreported token counts stay null. Payload capture defaults to off. Opt-in previews are allowlisted, redacted, and bounded before storage or export. |

## Scope limits

v0.1 covers saved traces and manual refresh. Async invocation, distributed and multi-agent tracing, live updates and heartbeats, token streaming, LangGraph checkpoints, OpenTelemetry export, automatic agent discovery, and cloud hosting are deferred. General task evaluation, run comparison, and fault injection are outside the product scope. The scripted failure scenario is a fixture for verifying the visualizer.

## Acceptance gates

These are the conditions for accepting each milestone.

| Milestone | Evidence required to pass |
|---|---|
| M0 · Setup | A clean environment installs from the Python 3.12 lockfile, imports the package, runs CLI help, and passes settings precedence, capture-default, offline test, lint, and formatting checks. Blocking design decisions are resolved. |
| M1 · Example | The same builder accepts scripted and live models. Without tracing, the scripted scenarios demonstrate success, propagated failure, and interruption. Independent assertions catch missing calls and incorrect tool results. |
| M2 · SDK | Real callbacks yield schema-valid sanitized JSON with distinct IDs, observed parents, timings, and statuses. Recovery retains the failed tool span. Missing evidence and unknown usage remain visible. Observer failures preserve the original result or exception. |
| M3 · Persistence | Reopening SQLite preserves completed, failed, interrupted, and unfinished work, including starts committed before a force-kill. Reads are stable, deletion affects only the selected run, and write-failure and secret-redaction checks pass. |
| M4 · Read API | Health, paginated history, and detail return schema-valid results for a real saved trace. Checks cover empty history, malformed requests, unknown IDs, unavailable storage, failed runs, partial traces, and unfinished spans. |
| M5 · Dashboard | From the UI alone, a developer can identify model/tool order, durations, failure location, and missing evidence. Duplicate names remain selectable. The UI handles missing data and recovers after an API failure. |
| M6 · Release | The offline suite, predeclared overhead budget, clean wheel installation, and fresh-checkout demo pass. The dashboard explains traces after restart. Any claim of live compatibility has sanitized provider-backed evidence. Record an unavailable live check as **not run**. Resolve known correctness and data-leak blockers before tagging `v0.1.0`. |

## Decisions for review

| Decision | Proposed default | When it matters |
|---|---|---|
| Which provider should the optional live example target? | Use one provider for which the developer has credentials. If there is no preference, use the OpenAI LangChain integration and select a tool-capable model through `AGENT_MODEL`. | Choose the integration before locking the `live` extra in M0.3. Offline verification uses the scripted model. |
| What tracing overhead is acceptable on the reference machine? | As an initial proposal for the short scripted success run, allow at most 50 ms added p95 elapsed time per invocation for each tracing mode versus tracing off. This budget is provisional. | Agree on and justify the budget before M6.2 measurements. Record the machine and workload so the result is reproducible. |

The record fields and lifecycle rules used by these gates are specified in the [architecture](architecture.md).
