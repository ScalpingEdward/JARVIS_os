# PHOENIX v21.223 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance

## Purpose
Consumes human-approved `approved-preview` evidence from v21.222 and governs creation of the next versioned recovery-reliability baseline candidate.

## Governance
- exact workspace, previous baseline and recovery-sequence lineage is preserved;
- candidate baseline version must equal previous version + 1;
- candidate baseline ID must be new and distinct from the previous baseline;
- candidate value delta is bounded by a configured maximum, default ±0.05;
- rollback lineage must bind exactly to the previous baseline ID/version/digest;
- preview digest and recovery-sequence digest are mandatory;
- duplicate committed sources and candidate-ID reuse fail closed;
- Risk Brain hard block propagates as `blocked`;
- deterministic candidate and audit digests are produced;
- final `committed` requires explicit human approval.

## State machine
`approved-preview` → `review-required` → human approval → `committed`.

Invalid lineage, replay, versioning or Risk Brain evidence → `blocked`. Excess candidate delta remains `review-required`.

## Boundary
This module commits governance evidence only. It does not activate the baseline, mutate consumers, route orders, execute trades, move funds, change permissions or actuate devices.

## Next
v21.224 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance.

## Demo countdown
After v21.223, 2 numbered modules remain through the v21.225 Demo 1 integration target.
