# PHOENIX v21.118 — Controlled Tool Invocation Gateway

## Purpose
v21.118 is the first gateway layer between an authorized sandbox request and an external adapter runtime. It validates policy, adapter binding, side-effect posture, budget, timeout, host restrictions and approval/authorization state before emitting a dispatch-ready contract.

## Invocation lifecycle
`review-required` → `approved` → `authorized` → `dispatch-ready` → `dispatched` → `succeeded|failed|timed-out`.

A dispatch token is created only after separate human approval and explicit authorization. Result ingestion requires the same workspace, the expected adapter identity and a dispatched invocation.

## Controls
- Tool and operation allow-lists
- Denied operations
- Allowed hosts
- Budget and timeout limits
- Side-effect classification
- Dry-run verification requirement for mutating operations
- Human approval and explicit authorization
- Adapter identity binding
- Dispatch token
- Result digest and execution receipt metadata
- Replay protection
- Workspace isolation
- Complete audit trail
- Risk Brain hard block

## Protected operations
Fund movement, order submission, trading execution, credential mutation, permission escalation and safety-control disabling are hard-blocked.

## Endpoints
- `GET /v1/tool-invocation-gateway/status`
- `POST /v1/tool-invocation-gateway/records`
- `GET /v1/tool-invocation-gateway/records`
- `GET /v1/tool-invocation-gateway/records/{record_id}`
- `POST /v1/tool-invocation-gateway/records/{record_id}/actions`
- `POST /v1/tool-invocation-gateway/records/{record_id}/result`
- `GET /v1/tool-invocation-gateway/audit`

## Safety boundary
The gateway and dispatch-contract lifecycle are enabled. The module itself does not embed an external network client and therefore does not directly call third-party systems. External adapter processes may consume a dispatch-ready contract only after all gates pass. Trading, fund movement and credential/safety-control mutation remain disabled and Risk Brain remains authoritative.

## Integration
v21.115 binds tasks to agents. v21.116 authorizes tool intent. v21.117 resolves an eligible adapter. v21.118 creates the final controlled invocation contract, dispatch token and result-receipt path. The next layer can add adapter worker execution and heartbeat/lease control behind this gateway.
