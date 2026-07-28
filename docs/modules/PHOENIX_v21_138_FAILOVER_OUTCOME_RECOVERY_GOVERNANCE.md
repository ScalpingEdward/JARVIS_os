# PHOENIX v21.138 — Failover Outcome Trust Feedback & Recovery-to-Primary Readiness Governance

## Purpose

PHOENIX v21.138 converts an approved v21.137 failover completion attestation into bounded trust feedback and a governed readiness decision for possible recovery to the primary path.

It does **not** mutate routing, execute recovery, expand permissions, perform external network calls, move funds, submit orders, or execute trades.

## Inputs

- v21.137 failover completion attestation ID and digest
- dispatch-plan ID and digest
- operation and target
- primary and standby adapter/worker identities
- failover completion, side-effect, receipt and standby stability evidence
- primary availability, latency, health and receipt-reconciliation evidence
- evidence confidence and freshness

## Scoring

The module computes:

- failover trust
- primary recovery readiness
- residual risk

Trust feedback is bounded. It can produce recommendations for human review, but it cannot autonomously change routing weights, policies, permissions, credentials or execution behavior.

## Recovery gates

A record may become `recovery-ready` only after:

1. evidence admission,
2. human review,
3. human approval,
4. failover trust threshold satisfaction,
5. primary recovery-readiness threshold satisfaction.

Low-trust or unhealthy-primary evidence remains in a governed hold/review state.

## Safety

Protected operations remain hard-blocked by the Risk Brain, including fund movement, order submission, trading execution, credential mutation, permission escalation and safety-control disabling.

Replay protection, workspace isolation, duplicate source-key protection and deterministic evidence/recovery digests are enforced.

## API

- `GET /v1/failover-outcome-recovery/status`
- `POST /v1/failover-outcome-recovery/records`
- `GET /v1/failover-outcome-recovery/records`
- `GET /v1/failover-outcome-recovery/records/{record_id}`
- `POST /v1/failover-outcome-recovery/records/{record_id}/actions`
- `GET /v1/failover-outcome-recovery/audit`

## Next

v21.139 should add Recovery-to-Primary Plan Governance, turning an approved `recovery-ready` record into a non-executing primary restoration plan with deterministic preconditions, rollback criteria and one-time authorization boundaries.
