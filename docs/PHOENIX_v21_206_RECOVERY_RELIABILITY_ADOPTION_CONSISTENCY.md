# PHOENIX v21.206 — Recovery Reliability Cross-Consumer Adoption Consistency & Drift Observation Governance

## Purpose
Observes human-approved `adopted` evidence from v21.205 across the complete expected consumer set and detects cross-consumer baseline adoption drift.

## Governance
- exact workspace and baseline ID/version/digest lineage;
- complete expected-consumer coverage;
- unexpected consumer rejection;
- one observation and unique receipt nonce per consumer;
- observation TTL/evidence-age enforcement;
- mandatory adopted + healthy state and minimum confidence;
- missing, stale, unhealthy, unadopted, low-confidence or lineage-mismatched evidence becomes `drift-detected`;
- duplicate observations/nonces, unexpected consumers, invalid admission, duplicate consistent source or Risk Brain hard block fail closed;
- deterministic consistency score and audit digest;
- final `consistent` requires explicit human approval.

## State machine
`adopted` → `review-required` → human approval → `consistent`

Consumer inconsistency → `drift-detected`. Invalid/replayed/high-risk evidence → `blocked`.

## Boundary
Observation governance only. This module does not mutate baselines or consumers, execute recovery, route orders, move funds, alter permissions or actuate devices.

## Next
v21.207 — Recovery Reliability Adoption Drift Escalation & Coordinated Reconciliation Readiness Governance.

## Demo countdown
After v21.206, 19 numbered modules remain through the v21.225 Demo 1 integration target.
