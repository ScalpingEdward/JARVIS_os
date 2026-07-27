# PHOENIX v21.112 — Change Proposal & Safe Execution Contract

## Purpose
v21.112 converts an approved optimization candidate from v21.111 into a strict, machine-readable and auditable change contract. It defines exactly what may change, under which preconditions, within which blast radius, with which validation evidence, rollback criteria, postconditions and human approvals.

## Contract domains
- Candidate and target-system identity
- Rationale and expected gain
- Validation confidence
- Blast-radius assessment
- Preconditions and postconditions
- Ordered change steps
- Reversibility coverage
- Dependency readiness
- Observability readiness
- Execution-window readiness
- Rollback readiness and rollback criteria
- Human approval and separate execution-contract authorization
- Replay protection and immutable audit trail

## Lifecycle
`draft`, `validated`, `review-required`, `approved`, `execution-ready`, `blocked`, `revoked`, `archived`.

`execution-ready` means only that the contract is approved for consumption by a later, separately permissioned runtime. It does not execute the change.

## API
- `GET /v1/change-proposals/status`
- `POST /v1/change-proposals/records`
- `GET /v1/change-proposals/records`
- `GET /v1/change-proposals/records/{record_id}`
- `POST /v1/change-proposals/records/{record_id}/actions`
- `GET /v1/change-proposals/audit`

## Safety boundary
This module does not mutate configuration, deploy code, shift traffic, restart runtimes, modify credentials or permissions, mutate portfolios or routing, move funds, submit orders or execute trades.

Human approval and a separate execution-contract authorization are mandatory. High blast radius combined with weak rollback readiness or extreme residual risk can trigger a Risk Brain hard block.

## Integration
v21.111 validates that a candidate is measurably better. v21.112 packages that candidate into a deterministic execution contract. The next runtime layer may consume this contract, but execution authority remains outside this module.
