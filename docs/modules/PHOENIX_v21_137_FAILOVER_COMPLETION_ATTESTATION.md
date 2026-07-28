# PHOENIX v21.137 — Governed Standby Dispatch Reconciliation & Failover Completion Attestation

## Purpose
v21.137 closes the governed failover loop after v21.136 consumes a one-time standby failover permit. It reconciles the downstream standby execution receipt against the exact approved failover authorization, dispatch plan, standby adapter/worker, gateway, operation and target.

## Controls
- consumed failover-permit verification
- authorization and dispatch-plan digest binding
- exact standby adapter/worker/gateway identity binding
- GET/HEAD-only read-only boundary
- response and receipt digest binding
- side-effect attestation for writes, credentials, permissions, fund movement, order submission and trading execution
- human approval before final attestation
- Risk Brain protected-operation hard blocks
- replay, workspace-isolation and duplicate-source protection
- immutable-style audit evidence

## Lifecycle
`blocked`, `evidence-ready`, `reconciled`, `review-required`, `approved`, `attested`, `mismatch`, `revoked`, `archived`.

## Endpoints
- `GET /v1/failover-completion-attestation/status`
- `POST /v1/failover-completion-attestation/records`
- `GET /v1/failover-completion-attestation/records`
- `GET /v1/failover-completion-attestation/records/{record_id}`
- `POST /v1/failover-completion-attestation/records/{record_id}/actions`
- `GET /v1/failover-completion-attestation/audit`

## Safety boundary
This module reconciles and attests only. It contains no external network client, performs no autonomous failover, cannot mutate routing or credentials, and cannot move funds, submit orders or execute trades.

## Next
v21.138 should add Failover Outcome Trust Feedback & Recovery-to-Primary Readiness Governance, using approved failover completion attestations as bounded evidence for future recovery planning without autonomous route mutation.
