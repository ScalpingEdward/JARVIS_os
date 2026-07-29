# PHOENIX v21.220 — Recovery Reliability Stability Observation & Episode Closure Governance

## Purpose
Consumes human-approved `completed` evidence from v21.219 and verifies post-recovery stability across every expected consumer before the recovery episode may close.

## Governance
- exact workspace and baseline ID/version/digest lineage;
- exact recovery-sequence digest binding to the authorized recovery plan;
- complete expected-consumer observation coverage;
- observation TTL/evidence-age validation;
- health and dependency satisfaction are hard requirements;
- latency quality, error quality, recovery quality and confidence feed deterministic per-consumer stability scores;
- any unhealthy or dependency-unsatisfied consumer forces `degraded`, regardless of aggregate score;
- per-consumer and episode-level stability thresholds;
- residual-risk ceiling;
- missing/stale/low-score/lineage-or-sequence-mismatched evidence remains `degraded`;
- unexpected or duplicate observations, invalid admission, duplicate closed source and Risk Brain hard block fail closed;
- final `closed` requires explicit human approval;
- deterministic audit digest.

## State machine
`completed` → `review-required` → human approval → `closed`.

Unstable evidence → `degraded`. Invalid/replayed/high-risk governance evidence → `blocked`.

## Boundary
Observation and closure governance only. No runtime recovery, baseline mutation, order execution, fund movement, permission changes or device actuation.

## Next
v21.221 — Recovery Reliability Outcome Learning & Baseline Feedback Governance.

## Demo countdown
After v21.220, 5 numbered modules remain through the v21.225 Demo 1 integration target.
