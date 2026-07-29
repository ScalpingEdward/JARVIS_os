# PHOENIX v21.201 — Recovery Reliability Outcome Learning & Baseline Feedback Governance

## Purpose
Consumes human-approved `closed` recovery episodes from v21.200 and derives bounded, auditable learning evidence for downstream baseline feedback simulation.

## Governance
- exact workspace and baseline ID/version/digest lineage is preserved;
- stability, aggregate confidence, recovery quality and residual risk are bound into a deterministic learning score;
- weak evidence remains `review-required`;
- feedback adjustment is bounded to ±0.05;
- Risk Brain hard blocks fail closed;
- duplicate approved sources are rejected;
- `approved-feedback` requires explicit human approval.

## State machine
`closed` → `review-required` → human approval → `approved-feedback`

Invalid admission, duplicate approved source or Risk Brain hard block → `blocked`.

## Boundary
This module does not change a committed or active baseline. `approved-feedback` is evidence only for the next impact-simulation and baseline-change-preview stage.

## Next
v21.202 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance.
