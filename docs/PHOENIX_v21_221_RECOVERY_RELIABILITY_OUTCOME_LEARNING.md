# PHOENIX v21.221 — Recovery Reliability Outcome Learning & Baseline Feedback Governance

## Purpose
Consumes human-approved `closed` recovery episodes from v21.220 and converts bounded post-recovery outcome evidence into auditable baseline feedback.

## Governance
- admission only from human-approved `closed` evidence;
- exact workspace, baseline and recovery-sequence lineage preservation;
- deterministic learning score from stability, confidence, recovery quality and inverse residual risk;
- feedback adjustment bounded to ±0.05;
- weak evidence remains `review-required`;
- separate human approval required before `approved-feedback`;
- duplicate approved sources fail closed;
- Risk Brain hard block fails closed;
- deterministic feedback and audit digests.

## State machine
`closed` → `review-required` → human approval → `approved-feedback`.

Invalid/replayed/hard-blocked evidence → `blocked`.

## Boundary
Learning/governance only. This module does not mutate a baseline, activate a candidate, change runtime consumers, route orders, move funds, change permissions or actuate devices.

## Next
v21.222 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance.

## Demo countdown
After v21.221, 4 numbered modules remain through the v21.225 Demo 1 integration target.
