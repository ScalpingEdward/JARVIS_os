# PHOENIX v21.204 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance

## Purpose
Consumes human-approved `committed` baseline artifacts from v21.203 and governs whether the committed recovery-reliability baseline is eligible for staged consumer adoption.

## Governance
- exact workspace/baseline/rollback lineage is preserved;
- candidate consumers must be unique and completely covered by rollout stages;
- rollout stages must be contiguous, ordered and non-overlapping;
- per-stage exposure limits bound rollout blast radius;
- eligibility requires explicit human approval;
- every rollout stage requires explicit approval before the artifact reaches `staged`;
- Risk Brain hard blocks fail closed;
- duplicate staged sources are rejected;
- deterministic audit digests preserve reviewability.

## State machine
`committed` → `review-required` → human eligibility approval → `eligible` → all stage approvals → `staged`.

Invalid admission, duplicate source, malformed coverage/order/overlap or Risk Brain hard block → `blocked`.

## Boundary
This module governs rollout eligibility and staged approval evidence only. It does not activate baselines, mutate consumers, route orders, move funds, change permissions or actuate devices.

## Next
v21.205 — Recovery Reliability Baseline Adoption Authorization & Receipt Governance.
