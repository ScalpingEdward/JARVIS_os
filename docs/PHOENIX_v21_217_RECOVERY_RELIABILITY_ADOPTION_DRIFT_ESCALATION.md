# PHOENIX v21.217 — Recovery Reliability Adoption Drift Escalation & Coordinated Reconciliation Readiness Governance

## Purpose
Consumes human-approved `drift-detected` evidence from v21.216 and turns it into bounded, auditable reconciliation-readiness evidence.

## Governance
- exact workspace and baseline ID/version/digest lineage;
- affected and healthy consumer sets are distinct and duplicate-free;
- every affected consumer carries an explicit drift reason, severity and confidence;
- deterministic blast-radius calculation;
- deterministic residual-risk calculation weighted by severity and confidence;
- configurable blast-radius and residual-risk ceilings;
- invalid admission, duplicate consumers, set overlap, replayed approved sources and Risk Brain hard blocks fail closed;
- explicit human approval is required before `reconciliation-ready`;
- deterministic audit digest.

## State machine
`drift-detected` → `review-required` → human approval → `reconciliation-ready`.

Policy/risk limit breaches remain `review-required`. Invalid/replayed governance evidence → `blocked`.

## Boundary
Governance only. This module does not reconcile, restart, roll back, mutate baselines, route orders, move funds, change permissions or actuate devices.

## Next
v21.218 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance.

## Demo countdown
After v21.217, 8 numbered modules remain through the v21.225 Demo 1 integration target.
