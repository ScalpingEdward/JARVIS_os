# PHOENIX v21.228 — Demo 1 Persistent Approval Inbox & Deferred Request Recovery Governance

## Purpose
Make Demo 1 approval-gated work survive process restarts and quiet-mode deferral instead of existing only in a response payload or in-memory queue.

## Added
- durable JSON-on-disk approval inbox with atomic file replacement;
- configurable storage path via `PHOENIX_DEMO1_APPROVAL_INBOX_PATH`;
- Demo 1 high-risk/gated requests are written to the durable inbox automatically;
- persistent states: `pending`, `deferred`, `resolved`, `blocked`;
- duplicate approval IDs are idempotent only when request identity matches;
- conflicting approval-ID reuse fails closed;
- deferred requests return to `pending` only after the quiet window ends and interaction is available;
- Risk Brain can block deferred recovery;
- recovery never performs autonomous execution;
- status/list/recovery/resolve endpoints are registered in the live FastAPI app;
- Demo runtime readiness now reports `approval_store_persistent = true`.

## API
- `GET /phoenix/demo1/v21.228/approvals/status`
- `GET /phoenix/demo1/v21.228/approvals`
- `POST /phoenix/demo1/v21.228/approvals/recover-deferred`
- `POST /phoenix/demo1/v21.228/approvals/{approval_id}/resolve`

## Important boundary
The durable inbox is an operator workflow/recovery surface. It does not replace canonical authorization semantics and it does not execute an approved action. A recovered request becomes `pending`, not executed.

`autonomous_high_risk_execution_enabled = false`

## Runtime readiness after v21.228
Completed Demo 1 hardening bindings:
- application router registration;
- STT/TTS provider/fallback contract;
- persistent approval inbox.

Remaining integration debt:
- memory-provider binding;
- operator UI/dashboard;
- concrete tool adapters.

## Next
v21.229 — Demo 1 Memory Provider Binding & Context Retrieval Governance.
