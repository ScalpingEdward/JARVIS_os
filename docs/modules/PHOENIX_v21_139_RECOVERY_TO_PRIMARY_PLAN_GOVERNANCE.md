# PHOENIX v21.139 — Recovery-to-Primary Plan Governance

## Purpose
Convert an approved `recovery-ready` outcome from v21.138 into a deterministic, human-approved, non-executing restoration plan for returning from the standby path to the primary path.

## Core controls
- Recovery-readiness record and digest binding
- Dispatch-plan record and digest binding
- Exact primary/standby adapter and worker identity binding
- Gateway identity binding
- Sandbox, gateway and worker policy-digest binding
- Primary availability, health, latency and receipt-reconciliation preconditions
- Failover-path stability and open-side-effect checks
- Deterministic rollback criteria
- Deterministic post-recovery validation checklist
- Confidence/freshness-weighted precondition assurance
- Human review and approval before `ready`
- Replay protection, workspace isolation and duplicate source-key protection
- Risk Brain hard blocks for protected operations

## Lifecycle
`blocked -> draft -> precondition-ready -> review-required -> approved -> ready`

Administrative terminal states: `revoked`, `archived`.

## Safety boundary
`ready` means only that a restoration plan has passed its governance gates. v21.139 does **not** mutate routing, execute failback, issue a network call, move funds, submit orders, execute trades, expand permissions or change credentials.

## Endpoints
- `GET /v1/recovery-primary-plans/status`
- `POST /v1/recovery-primary-plans/records`
- `GET /v1/recovery-primary-plans/records`
- `GET /v1/recovery-primary-plans/records/{record_id}`
- `POST /v1/recovery-primary-plans/records/{record_id}/actions`
- `GET /v1/recovery-primary-plans/audit`

## Integration
v21.137 attests governed failover completion. v21.138 scores the failover outcome and determines whether primary recovery is ready for human-reviewed planning. v21.139 converts that readiness into a bounded restoration plan with explicit preconditions, rollback criteria and validation checks.

## Next
v21.140 should add One-Time Recovery Permit & Primary Handoff Governance, binding a `ready` v21.139 plan to the exact primary adapter/worker/gateway chain and issuing a short-lived single-use recovery permit without bypassing sandbox, gateway, worker or receipt controls.
