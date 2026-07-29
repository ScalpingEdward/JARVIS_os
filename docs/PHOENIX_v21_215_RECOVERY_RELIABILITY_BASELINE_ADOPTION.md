# PHOENIX v21.215 — Recovery Reliability Baseline Adoption Authorization & Receipt Governance

## Purpose
Consumes human-approved `staged` rollout evidence from v21.214 and governs per-consumer baseline adoption with explicit authorization, fresh receipts and final human approval.

## Governance
- exact workspace, candidate-baseline and rollback lineage is preserved;
- adoption is scoped to one target consumer per decision;
- authorization is separate from receipt acceptance;
- receipt consumer identity must match the target consumer;
- receipt baseline ID/version/digest and rollback lineage must match exactly;
- receipt TTL/evidence age is enforced;
- receipt nonce replay is rejected;
- `adopted + healthy + minimum confidence` are mandatory;
- duplicate source-consumer adoption is rejected;
- Risk Brain hard blocks fail closed;
- final `adopted` requires explicit human approval;
- deterministic audit digest.

## State machine
`staged` → `review-required` → authorization → `authorized` → receipt → `receipt-required` → human approval → `adopted`.

Invalid/replayed/high-risk evidence → `blocked`.

## Boundary
Governance and receipt validation only. This module does not mutate a consumer, activate a baseline, execute orders, move funds, change permissions or actuate devices.

## Next
v21.216 — Recovery Reliability Cross-Consumer Adoption Consistency & Drift Observation Governance.

## Demo countdown
After v21.215, 10 numbered modules remain through the v21.225 Demo 1 integration target.
