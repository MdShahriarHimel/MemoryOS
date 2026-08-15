# Session Replay

Session replay reconstructs what an agent did during a session: the retrievals it
ran, the context bundles MEMORY OS assembled, and the memories it wrote — on a
scrubable timeline.

## Data model
`sessions` and `session_events` (append-only) hold the ordered event stream. Each
event carries a monotonic `seq`, a `t` offset (seconds from session start), a
`type` (`request`, `search`, `context`, `response`, `memory_write`), a short
`detail`, and optional `latency_ms`.

## UI
`/replay` provides play/pause, a timeline scrubber, and 0.5x–4x speed. Events
reveal progressively as the playhead advances. Until a real session is loaded the
page shows an **honest empty state** — it never fabricates events.
