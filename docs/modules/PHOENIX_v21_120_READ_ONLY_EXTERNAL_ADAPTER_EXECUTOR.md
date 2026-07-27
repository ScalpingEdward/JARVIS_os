# PHOENIX v21.120 — Read-Only External Adapter Executor

## Purpose
v21.120 introduces the first narrowly scoped external execution boundary in PHOENIX. It is intentionally limited to read-only operations and sits behind the complete v21.116-v21.119 authorization chain.

## Core controls
- GET/HEAD only
- Read-only side-effect posture
- Egress host allow-listing
- Host pinning
- Explicit operation allow-listing
- Denied path prefixes
- Strict timeouts
- Response-size limits
- No redirect following by default
- Human approval and separate authorization
- Worker and adapter identity binding
- Gateway/dispatch-token binding metadata
- Replay protection
- Workspace isolation
- Immutable-style execution receipt digest
- Response digest, byte count and duration capture

## Lifecycle
`review-required` → `approved` → `authorized` → `ready` → `running` → `succeeded|failed|timed-out`.

Administrative terminal states include `cancelled`, `revoked` and `archived`. Critical policy violations are `blocked`.

## API
- `GET /v1/read-only-adapter-executor/status`
- `POST /v1/read-only-adapter-executor/records`
- `GET /v1/read-only-adapter-executor/records`
- `GET /v1/read-only-adapter-executor/records/{record_id}`
- `POST /v1/read-only-adapter-executor/records/{record_id}/actions`
- `POST /v1/read-only-adapter-executor/records/{record_id}/result`
- `GET /v1/read-only-adapter-executor/audit`

## Safety boundary
v21.120 is the first executor contract that permits external read operations, but PHOENIX still hard-blocks fund movement, order submission, trading execution, credential mutation, permission escalation and safety-control disabling. Write-capable HTTP methods are excluded from the schema and runtime contract.

The module does not embed secrets into records. External worker implementations must resolve credential references outside PHOENIX core and remain constrained by the adapter registry, invocation gateway and worker lease chain.

## Integration
- v21.116 authorizes tool intent.
- v21.117 resolves an eligible adapter.
- v21.118 creates the dispatch contract.
- v21.119 governs worker lease, heartbeat and execution state.
- v21.120 adds the first safe read-only external execution contract and immutable result receipts.

## Next
v21.121 should add read-only connector policy profiles and response sanitization/schema validation so different external services can be used without weakening the common executor boundary.
