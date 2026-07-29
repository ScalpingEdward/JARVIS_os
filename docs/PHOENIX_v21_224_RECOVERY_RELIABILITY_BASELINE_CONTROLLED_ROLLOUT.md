# PHOENIX v21.224 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance

## Purpose
Consumes human-approved `committed` baseline-candidate evidence from v21.223 and governs bounded rollout eligibility across the complete candidate-consumer set.

## Governance
- exact workspace, candidate baseline, rollback baseline and recovery-sequence lineage;
- complete candidate-consumer coverage exactly once across rollout stages;
- contiguous deterministic stage ordering;
- duplicate or overlapping stage consumers fail closed;
- configurable maximum exposure per stage;
- separate human approval before eligibility;
- stage approvals must form an ordered prefix;
- all stages must be approved before final `staged` evidence;
- duplicate staged-source protection;
- Risk Brain hard blocks fail closed;
- deterministic rollout and audit digests.

## State machine
`committed` → `review-required` → human approval → `eligible` → ordered stage approvals → `staged`.

Invalid admission, duplicate consumers, coverage mismatch, out-of-order approvals, replayed staged source or Risk Brain hard block → `blocked`. Exposure-limit breaches remain `review-required`.

## Boundary
Governance only. This module does not activate a baseline, mutate consumers, execute recovery, route orders, move funds, change permissions or actuate devices.

## Next
v21.225 — PHOENIX Demo 1 Vertical Slice Integration & Operator Experience Governance.

## Demo countdown
After v21.224, one numbered target remains: v21.225 Demo 1 integration.
