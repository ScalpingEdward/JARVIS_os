# PHOENIX v21.147 — Baseline Consumer Adoption Receipt & Drift Monitoring Governance

v21.147 requires every allow-listed downstream governance consumer to acknowledge the exact reliability baseline identity, version and digest that it has adopted.

## Flow

`Approved Preview → Controlled Rollout → Active Consumer → Adoption Receipt → Drift Detection → Human Review`

## Guarantees

- admission only from active v21.146 rollout evidence
- consumer type must be supported and explicitly allow-listed
- exact baseline ID, version and digest are reconciled
- version/digest/identity mismatch produces `drift-detected`
- Risk Brain hard blocks propagate
- duplicate source keys are rejected per workspace
- workspace mismatch fails closed
- deterministic adoption-receipt digests and audit events are preserved
- drift can be marked reviewed only with explicit human review

## Safety boundary

This module does not correct drift automatically. It does not mutate baselines, routing, policies, credentials, permissions or execution settings, and it performs no external network call.

## Next

v21.148 should add Drift Escalation, Consumer Quarantine & Re-Adoption Governance, allowing a human-reviewed drift event to quarantine an affected governance consumer from using the baseline until a fresh exact-version adoption receipt is approved.
