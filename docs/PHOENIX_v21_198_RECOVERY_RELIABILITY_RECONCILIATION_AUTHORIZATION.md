# PHOENIX v21.198 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance

## Purpose
Consumes human-approved `reconciliation-ready` evidence from v21.197 and produces a bounded, explicitly authorized, ordered consumer-recovery plan.

## Governance
- exact workspace and baseline lineage is preserved;
- healthy consumers are preserved and may not overlap the affected set;
- every affected consumer must appear exactly once in the recovery sequence;
- recovery ordering must be contiguous and deterministic;
- blast-radius and residual-risk ceilings are enforced before readiness;
- a separate human authorization is required before recovery staging;
- each recovery step must be approved in order;
- out-of-order approval fails closed;
- Risk Brain hard blocks remain authoritative;
- duplicate completed source evidence is rejected;
- audit and sequence digests are deterministic.

## Lifecycle
`reconciliation-ready → review-required → authorized → staged → recovery-ready`

Invalid lineage, sequence mismatch, overlap, duplicate evidence or Risk Brain hard block → `blocked`.

## Boundary
This module authorizes and stages recovery governance only. It does not restart consumers, mutate baselines, execute recovery, route orders, move funds, change credentials or actuate devices.

## Next
v21.199 — Recovery Reliability Recovery Receipt Reconciliation & Cross-Consumer Completion Governance.
