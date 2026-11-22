# Agent Reliability Lab

Build the **Agent Execution Visualizer v0.1**. A developer should be able to run a local Python agent, open its saved trace, and see which model and tools ran, how long each call took, and where a failure occurred.

## Work one roadmap step at a time

1. Open [the implementation roadmap](arl-v0.1-implementation-roadmap.md). Use **Foundations** for the design and the numbered step for its tasks and verification checklist. On a new checkout, begin at **M0.1**. As they become available, read `docs/mvp.md` for scope, `docs/architecture.md` for design decisions, and `docs/progress.md` for the last verified step.
2. Identify the requested step, its deliverable, and how to check it. Inspect the relevant files and existing work. Create each component at the step assigned in the repository map. For example, M0.1 produces two design documents. Package scaffolding starts at M0.2.
3. Complete the step and run its checks. Explain the result in plain language and pause for the developer to review before starting the next numbered step. At the end of a milestone, check its exit criteria as well.

## Keep the components independent

- Keep the generic example in `examples/toy_agent/`. It can import the SDK. The SDK must work independently of the example.
- Keep the collector and its Run/Span models independent of LangChain. Translate LangChain callbacks in the adapter. Use observed callback IDs to link operations to their parents, including when two calls use the same tool name.
- Write sanitized records through the storage interface. In v0.1, the tracer runs with the agent and writes to local SQLite. FastAPI reads saved traces. The Streamlit dashboard gets its data through the read-only HTTP API.

## Preserve what actually happened

- A **run** is one invocation. A **span** is one operation inside it. If a tool fails and the agent recovers, keep the tool span failed and mark the normally returned run completed. Verify task correctness separately with an outcome test.
- If a start was recorded but the finish is missing after a crash, keep the end time unknown. Display **unfinished / liveness unknown**. Record an interruption when the wrapper observes it. Keep unreported token counts null.
- If tracing loses evidence, issue a safe diagnostic and mark the trace partial where possible. Preserve the agent’s return value or re-raise its original exception.
- Keep payload capture off by default. Apply the M2.5 allowlist, recursive redaction, and size/depth limits before storage or export. Use safe error summaries. Keep credentials, local databases, and trace exports out of Git.

## Verify and hand off

Use the current step’s checklist, including document review for M0.1. From M0.4 onward, use these repository checks for the offline suite, lint, and formatting:

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Keep offline tests independent of provider credentials. Report a live check as **not run** if it was skipped. If a check fails, reproduce the failure, fix its cause within the step, and rerun it.

Review the diff before committing. Follow the roadmap’s branch-per-milestone workflow and keep each commit focused on a verified change. Include `uv.lock` with dependency changes. Starting at M0.4, record the step ID, changed files, commands and observed results, outstanding checks, relevant commit if available, and next step in `docs/progress.md`. Before that file exists, give the handoff in chat.
