# PHOENIX v21.141 — Governed Primary Recovery Reconciliation & Recovery Completion Attestation

v21.141 closes the recovery-to-primary control loop after a v21.140 one-time recovery permit has been consumed.

## Flow

`Recovery Ready → Recovery Plan → One-Time Permit → Primary Handoff → Receipt → Reconciliation → Human Approval → Recovery Attested`

## Guarantees

- consumed recovery permit is required
- recovery-plan digest is bound to the downstream receipt
- primary adapter, worker and gateway identities must match
- only read-only GET/HEAD operations can attest successfully
- writes, route changes, credential/permission changes, fund movement, orders and trading execution fail closed
- upstream Risk Brain hard blocks propagate
- clean reconciliation still requires explicit human approval
- source-key replay protection and workspace isolation are enforced
- deterministic permit, receipt and attestation digests provide audit evidence

## Non-goals

This module performs no network call, no route mutation and no failback execution. It only reconciles downstream evidence and produces a governed completion attestation.

## Next

v21.142 should add Recovery Stability Observation & Primary Route Confidence Governance: a bounded observation window after an attested recovery, with health/latency/reconciliation sampling and human-reviewed confidence before the failover episode is considered fully closed.
