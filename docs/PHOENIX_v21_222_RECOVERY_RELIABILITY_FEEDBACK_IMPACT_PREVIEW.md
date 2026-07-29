# PHOENIX v21.222 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance

## Purpose
Consumes human-approved `approved-feedback` evidence from v21.221 and simulates the bounded effect of the proposed baseline feedback before any new versioned baseline can be committed.

## Governance
- exact workspace, baseline ID/version/digest and recovery-sequence lineage preservation;
- feedback adjustment bounded to ±0.05 by schema;
- candidate value clamped to `[0.0, 1.0]`;
- projected score, rank, failover readiness and recovery readiness are computed deterministically;
- blast-radius and residual-risk ceilings prevent approval;
- invalid source admission, duplicate approved source or Risk Brain hard block fail closed;
- final `approved-preview` requires explicit human approval;
- preview and audit digests are deterministic.

## State machine
`approved-feedback` → `review-required` → human approval → `approved-preview`.

Risk/limit violations remain `review-required`; invalid/replayed/hard-block evidence → `blocked`.

## Boundary
Simulation and preview governance only. This module does not commit, activate or mutate any live baseline, consumer, route, order, fund, permission or device.

## Next
v21.223 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance.

## Demo countdown
After v21.222, 3 numbered modules remain through the v21.225 Demo 1 integration target.
