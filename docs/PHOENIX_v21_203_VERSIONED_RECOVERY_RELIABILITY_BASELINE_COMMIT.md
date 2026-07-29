# PHOENIX v21.203 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance

## Purpose
Consumes human-approved `approved-preview` evidence from v21.202 and creates a versioned, human-controlled recovery reliability baseline commit artifact.

## Governance
- exact workspace, preview and baseline lineage is preserved;
- proposed version must be exactly `previous_version + 1`;
- candidate value must exactly match the approved preview candidate;
- absolute candidate delta is capped at `0.05`;
- candidate value remains inside `[0.0, 1.0]` through schema validation;
- rollback version and rollback value are bound exactly to the previous baseline;
- duplicate approved sources and duplicate previews fail closed;
- deterministic candidate-baseline and audit digests are produced;
- Risk Brain hard block propagates;
- final `committed` state requires explicit human approval.

## State machine
`approved-preview` → `review-required` → human approval → `committed`

Invalid lineage, replay, versioning, preview binding, rollback binding, candidate-delta violation or Risk Brain hard block → `blocked`.

## Boundary
`committed` means a versioned baseline artifact was approved. This module does not activate the baseline, mutate runtime consumers, route orders, move funds, change permissions or actuate devices.

## Next
v21.204 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance.
