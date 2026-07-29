# PHOENIX v21.210 — Recovery Reliability Stability Observation & Episode Closure Governance

## Purpose
Consumes human-approved `completed` evidence from v21.209 and verifies post-recovery stability across every expected consumer before an episode may close.

## Governance
- exact workspace and baseline lineage;
- complete expected-consumer observation coverage;
- freshness/TTL validation;
- health and dependency satisfaction are hard requirements;
- latency quality, error quality and confidence feed a deterministic stability score;
- any unhealthy or dependency-unsatisfied consumer forces `degraded`, even when aggregate quality remains high;
- residual risk must remain within its configured ceiling;
- unexpected/duplicate observations, invalid admission, duplicate closed source and Risk Brain hard block fail closed;
- final `closed` requires explicit human approval;
- deterministic audit digest.

## State machine
`completed` → `review-required` → human approval → `closed`.

Unstable evidence → `degraded`. Invalid/replayed/high-risk governance evidence → `blocked`.

## Boundary
Observation and closure governance only. No runtime recovery, baseline mutation, order execution, fund movement, permission changes or device actuation.

## Next
v21.211 — Recovery Reliability Outcome Learning & Baseline Feedback Governance.

## Demo countdown
After v21.210, 15 numbered modules remain through the v21.225 Demo 1 integration target.
