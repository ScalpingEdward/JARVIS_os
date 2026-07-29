# PHOENIX v21.214 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance

## Purpose
Consumes human-approved `committed` baseline evidence from v21.213 and governs controlled rollout eligibility across candidate consumers.

## Governance
- exact workspace, baseline and rollback lineage is preserved;
- candidate consumers must be unique and non-empty;
- rollout stages must be contiguous, ordered and non-overlapping;
- all candidate consumers must be covered exactly once;
- each stage has an explicit maximum exposure limit;
- human approval is required before rollout eligibility;
- stage approvals must proceed in order;
- all stages must be approved before final `staged`;
- duplicate staged sources and Risk Brain hard blocks fail closed;
- rollout and audit digests are deterministic.

## State machine
`committed` → `review-required` → human approval → `eligible` → ordered stage approvals → `staged`.

Invalid lineage/admission, overlap, duplicate consumers, coverage failure, out-of-order approval, replay or Risk Brain hard block → `blocked`. Exposure-limit violations remain `review-required`.

## Boundary
Governance only. This module does not activate a baseline, mutate consumers, route orders, move funds, change permissions or actuate devices.

## Next
v21.215 — Recovery Reliability Baseline Adoption Authorization & Receipt Governance.

## Demo countdown
After v21.214, 11 numbered modules remain through the v21.225 Demo 1 integration target.
