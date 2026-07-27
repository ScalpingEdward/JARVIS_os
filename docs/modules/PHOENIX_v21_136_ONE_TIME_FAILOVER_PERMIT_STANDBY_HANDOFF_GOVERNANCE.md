# PHOENIX v21.136 — One-Time Failover Permit & Standby Handoff Governance

## Purpose
v21.136 converts a governed `failover-authorized` decision from v21.135 into a short-lived, single-use standby handoff permit. The module binds the failover authorization, dispatch plan, standby adapter/worker, gateway and execution-policy digests before any downstream failover execution can be considered.

## Core guarantees
- Admission requires an upstream failover authorization.
- Protected operations and upstream Risk Brain blocks fail closed.
- Human review and approval are mandatory before permit issuance.
- Permit issuance creates a deterministic token digest.
- Permit consumption is single-use.
- Consumption verifies authorization, adapter, worker and gateway bindings.
- Workspace isolation, replay protection and duplicate source-key protection are enforced.
- Audit events preserve permit lifecycle and handoff evidence.

## Lifecycle
`blocked` → `authorized` → `review-required` → `approved` → `issued` → `consumed`

Terminal/administrative states: `expired`, `revoked`, `archived`.

## Endpoints
- `GET /v1/failover-permit-handoff/status`
- `POST /v1/failover-permit-handoff/records`
- `GET /v1/failover-permit-handoff/records`
- `GET /v1/failover-permit-handoff/records/{permit_id}`
- `POST /v1/failover-permit-handoff/records/{permit_id}/actions`
- `POST /v1/failover-permit-handoff/records/{permit_id}/consume`
- `GET /v1/failover-permit-handoff/audit`

## Safety boundary
This module governs authorization and handoff only. It does not perform an external network call, mutate routing, expand permissions, move funds, submit orders, or execute trades. Consuming a permit authorizes a downstream controlled handoff; it is not itself failover execution.

## Integration
v21.134 creates the approved primary/standby plan. v21.135 verifies runtime degradation and produces the governed failover authorization. v21.136 binds that authorization to the exact standby execution identities and issues a one-time permit without bypassing sandbox, gateway, worker or receipt-reconciliation controls.

## Next
v21.137 should add Governed Standby Dispatch Reconciliation & Failover Completion Attestation, reconciling the one-time standby handoff with the downstream receipt and proving that the failover remained within the approved read-only boundary.
