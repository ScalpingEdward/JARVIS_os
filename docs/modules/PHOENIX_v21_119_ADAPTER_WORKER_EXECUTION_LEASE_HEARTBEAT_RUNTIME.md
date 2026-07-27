# PHOENIX v21.119 — Adapter Worker Execution & Lease/Heartbeat Runtime

## Purpose
v21.119 introduces the worker-side runtime contract behind the v21.118 Controlled Tool Invocation Gateway. It manages worker assignment, short-lived leases, heartbeats, result receipts and stale-worker detection without embedding an external connector client in the PHOENIX core.

## Runtime chain
`planner -> orchestrator -> sandbox -> adapter registry -> invocation gateway -> adapter worker runtime`

## Core controls
- Gateway record and dispatch-token binding
- Worker identity binding
- Short-lived lease token
- Lease expiration tracking
- Heartbeat-based liveness
- Attempt accounting
- Result receipt validation
- Output digest, duration and cost metadata
- Replay protection
- Workspace isolation
- Duplicate source-key protection
- Risk Brain hard blocks
- Complete audit trail with event digests

## States
`blocked`, `pending`, `leased`, `running`, `heartbeat-missed`, `succeeded`, `failed`, `timed-out`, `cancelled`, `revoked`, `archived`.

## API
- `GET /v1/adapter-worker-runtime/status`
- `POST /v1/adapter-worker-runtime/records`
- `GET /v1/adapter-worker-runtime/records`
- `GET /v1/adapter-worker-runtime/records/{record_id}`
- `POST /v1/adapter-worker-runtime/records/{record_id}/lease`
- `POST /v1/adapter-worker-runtime/records/{record_id}/heartbeat`
- `POST /v1/adapter-worker-runtime/records/{record_id}/result`
- `POST /v1/adapter-worker-runtime/records/{record_id}/actions`
- `GET /v1/adapter-worker-runtime/audit`

## Safety boundary
The runtime governs leases, liveness and result receipts. It does **not** contain a network client for external adapter invocation. Fund movement, order submission, trading execution, credential mutation, permission escalation and safety-control disabling remain prohibited and are subject to Risk Brain hard block.

## Next
v21.120 should add the first narrowly-scoped external adapter executor for read-only connectors behind the full v21.116-v21.119 authorization chain, with host pinning, response-size limits, egress policy and immutable execution receipts.
