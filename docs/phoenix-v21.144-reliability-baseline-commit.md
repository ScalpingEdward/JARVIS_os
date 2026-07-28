# PHOENIX v21.144 — Human-Approved Reliability Baseline Commit & Versioned Rollback Governance

v21.144 converts a bounded reliability proposal from a human-approved v21.143 incident closure into a separately reviewed, versioned baseline record.

## Flow

`Incident Closed → Baseline Proposal → Human Approval → Active Version`

Rollback is also separately governed:

`Active Version → Rollback Proposal → Human Approval → New Active Rollback Version`

## Guarantees

- only human-approved closed incident evidence is admitted
- workspace binding and operation replay protection are enforced
- Risk Brain hard blocks propagate
- baseline values are constrained to `[0.0, 1.0]`
- every activation creates an explicit versioned record
- previous version/value metadata is retained
- rollback never rewrites history; it creates a new version pointing to an older target
- proposal and rollback activation require separate human approval
- deterministic digests and audit events preserve traceability

## Safety boundary

This module does not change routing weights, execution policy, permissions, credentials, adapter configuration, worker configuration, fund movement, order submission, or trading execution.

## Next

v21.145 should add Baseline Impact Simulation & Change-Control Preview Governance, evaluating the effect of a newly active reliability baseline on candidate ranking and failover thresholds in simulation only before any downstream policy consumer may use it.
