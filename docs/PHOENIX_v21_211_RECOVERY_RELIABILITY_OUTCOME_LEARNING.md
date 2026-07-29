# PHOENIX v21.211 — Recovery Reliability Outcome Learning & Baseline Feedback Governance

## Purpose
Consumes human-approved `closed` evidence from v21.210 and derives bounded, auditable feedback for downstream baseline-change simulation.

## Governance
- exact workspace and baseline lineage is retained;
- stability score, aggregate confidence, recovery quality and residual risk are bound into a deterministic learning score;
- weak learning evidence or excessive residual risk remains `review-required`;
- feedback adjustment is bounded to an absolute maximum of `0.05`;
- candidate feedback value must remain inside `[0.0, 1.0]`;
- Risk Brain hard blocks and invalid/duplicate sources fail closed;
- final `approved-feedback` requires explicit human approval;
- feedback and audit digests are deterministic.

## State machine
`closed` → `review-required` → human approval → `approved-feedback`.

Invalid/replayed/out-of-range/high-risk governance evidence → `blocked` or remains `review-required` as appropriate.

## Boundary
Learning/governance only. This module does not mutate, activate or commit a baseline and performs no runtime execution, fund movement, permission changes or device actuation.

## Next
v21.212 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance.

## Demo countdown
After v21.211, 14 numbered modules remain through the v21.225 Demo 1 integration target.
