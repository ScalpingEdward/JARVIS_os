# PHOENIX v21.213 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance

## Purpose
Consumes human-approved `approved-preview` evidence from v21.212 and produces a versioned, rollback-bound baseline candidate commit record.

## Governance
- exact workspace, preview and previous-baseline lineage;
- candidate version must equal previous version + 1;
- rollback version/value must exactly match the previous baseline;
- candidate value remains within `[0.0, 1.0]` and delta is capped at `0.05`;
- candidate baseline ID may not reuse the previous baseline ID;
- duplicate source and duplicate preview protection;
- deterministic candidate and audit digests;
- final `committed` requires explicit human approval;
- Risk Brain hard blocks fail closed.

## State machine
`approved-preview` → `review-required` → human approval → `committed`.

Invalid lineage, replay, versioning, rollback, delta or Risk Brain evidence → `blocked`.

## Boundary
Commit governance only. `committed` records a controlled candidate baseline version; it does not activate the baseline or mutate runtime consumers.

## Next
v21.214 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance.

## Demo countdown
After v21.213, 12 numbered modules remain through the v21.225 Demo 1 integration target.
