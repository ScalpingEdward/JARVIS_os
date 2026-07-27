# PHOENIX v21.127 — Proposal-to-Safe-Execution Contract Binding

## Purpose
v21.127 binds an authorized v21.126 action proposal to an existing safe-execution contract without allowing any bypass of the sandbox, adapter, gateway or worker controls.

## Core guarantees
- Proposal record and digest binding
- Safe-execution contract ID and digest binding
- Sandbox, adapter, gateway and worker policy-chain binding
- Operation and target binding
- Binding integrity digest
- Human approval before binding
- Replay protection, workspace isolation and audit digests
- Risk Brain hard blocks for protected operations and direct execution requests

## Lifecycle
`blocked`, `review-required`, `approved`, `bound`, `ready`, `revoked`, `archived`.

## Safety boundary
`ready` means the proposal and safe-execution contract are cryptographically and procedurally bound. It does not execute the operation. Execution remains disabled in this module and must still pass the downstream v21.116-v21.120 sandbox, adapter, gateway, worker and external-executor controls.

## API
- `GET /v1/proposal-execution-binding/status`
- `POST /v1/proposal-execution-binding/records`
- `GET /v1/proposal-execution-binding/records`
- `GET /v1/proposal-execution-binding/records/{record_id}`
- `POST /v1/proposal-execution-binding/records/{record_id}/actions`
- `GET /v1/proposal-execution-binding/audit`

## Next
v21.128 should add End-to-End Execution Authorization Chain Verification, verifying the complete decision → proposal → binding → sandbox → adapter → gateway → worker chain before any controlled read-only dispatch is eligible.
