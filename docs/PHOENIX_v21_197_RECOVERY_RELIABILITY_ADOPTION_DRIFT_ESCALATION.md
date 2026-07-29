# PHOENIX v21.197 — Recovery Reliability Adoption Drift Escalation & Coordinated Reconciliation Readiness Governance

## Purpose
Consumes human-approved `drift-detected` evidence from v21.196 and produces bounded, auditable reconciliation-readiness evidence.

## Governance
- exact workspace and baseline lineage is preserved;
- affected and healthy consumer sets are separated and overlap is rejected;
- every affected consumer carries an explicit drift reason, severity and confidence;
- blast radius and residual risk are computed deterministically;
- configured blast-radius and residual-risk ceilings prevent readiness;
- Risk Brain hard blocks fail closed;
- duplicate approved sources are rejected;
- `reconciliation-ready` requires an explicit human approval.

## State machine
`drift-detected` → `review-required` → human approval → `reconciliation-ready`

Invalid admission, duplicate approved evidence, consumer-set overlap or Risk Brain hard block → `blocked`.

## Boundary
This module does not reconcile, restart, activate, roll back or mutate any consumer or baseline. It only produces governance evidence for the ordered recovery authorization stage.

## Next
v21.198 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance.
