# PHOENIX v21.200 — Recovery Reliability Stability Observation & Episode Closure Governance

## Purpose
Consumes human-approved `completed` recovery evidence from v21.199 and observes the complete recovered consumer set before an episode may be closed.

## Governance
- exact workspace and baseline ID/version/digest lineage;
- complete expected-consumer observation coverage;
- per-consumer health and dependency-satisfaction hard checks;
- latency quality, error quality and confidence scoring;
- observation TTL/evidence-age enforcement;
- deterministic aggregate stability score and residual risk;
- any unhealthy or dependency-unsatisfied consumer forces `degraded` regardless of aggregate score;
- missing, stale or lineage-mismatched evidence also forces `degraded`;
- invalid admission, unexpected/duplicate observations, duplicate closed source or Risk Brain hard block fail closed;
- final `closed` requires explicit human approval.

## State machine
`completed` → `review-required` → human approval → `closed`

Instability → `degraded`. Invalid/replayed/high-risk evidence → `blocked`.

## Boundary
Observation/governance only. This module does not mutate consumers, activate or roll back baselines, execute trades, move funds, change permissions or actuate devices.

## Next
v21.201 — Recovery Reliability Outcome Learning & Baseline Feedback Governance.
