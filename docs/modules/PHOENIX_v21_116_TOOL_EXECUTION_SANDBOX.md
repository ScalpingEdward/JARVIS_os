# PHOENIX v21.116 — Tool Execution Sandbox

## Purpose
v21.116 introduces the controlled execution boundary between the multi-agent orchestrator and future real tool adapters. It defines an auditable sandbox contract for tool calls before external side effects are enabled.

## Core controls
- Tool and operation allow-lists
- Explicit deny-lists
- Permission scopes
- Side-effect classification
- Human approval and separate authorization
- Dry-run default
- Timeout limits
- Per-task call limits
- Budget limits
- Confidence thresholds
- Kill switch
- Replay protection
- Workspace isolation
- Execution receipts and output digests
- Risk Brain hard blocks

## Lifecycle
`review-required -> approved -> ready -> running -> succeeded/failed/timed-out`

Additional terminal states: `blocked`, `cancelled`, `revoked`, `archived`.

## API
- `GET /v1/tool-execution-sandbox/status`
- `POST /v1/tool-execution-sandbox/records`
- `GET /v1/tool-execution-sandbox/records`
- `GET /v1/tool-execution-sandbox/records/{record_id}`
- `POST /v1/tool-execution-sandbox/records/{record_id}/actions`
- `POST /v1/tool-execution-sandbox/records/{record_id}/result`
- `GET /v1/tool-execution-sandbox/audit`

## Safety boundary
v21.116 enables the sandbox lifecycle and dry-run receipts, but keeps real external adapter execution disabled. Fund movement, order submission and trading execution are hard-blocked. Credential/safety-control mutation is also hard-blocked.

This separation lets the orchestrator exercise approval, authorization, timeout, budget, call-limit and receipt paths without granting uncontrolled external side effects.

## Integration
v21.115 binds tasks to eligible agents. v21.116 adds the permissioned tool-call boundary. A later module can attach concrete tool adapters to this sandbox while preserving the same authorization and receipt contract.
