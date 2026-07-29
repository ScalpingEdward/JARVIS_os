# PHOENIX v21.205 — Recovery Reliability Baseline Adoption Authorization & Receipt Governance

## Purpose
Consumes human-approved `staged` rollout evidence from v21.204 and governs per-consumer baseline adoption through explicit authorization and a fresh adoption receipt.

## Governance
- exact workspace, consumer, baseline ID/version/digest and rollback lineage;
- separate authorization before adoption evidence is accepted;
- fresh receipt TTL/evidence-age enforcement;
- unique receipt nonce and replay protection;
- `adopted`, `healthy` and minimum confidence are mandatory;
- receipt lineage must exactly match the authorized adoption target;
- final `adopted` requires explicit human approval of the receipt;
- duplicate source-consumer adoption is rejected;
- Risk Brain hard blocks fail closed;
- deterministic audit digest.

## State machine
`staged` → `review-required` → authorization → `receipt-required` → receipt review → `authorized` → human receipt approval → `adopted`.

Invalid admission, stale/replayed/mismatched/unhealthy evidence or Risk Brain hard block → `blocked`.

## Boundary
Governance only. This module does not activate or mutate a live runtime consumer, execute trades, move funds, change permissions or actuate devices.

## Next
v21.206 — Recovery Reliability Cross-Consumer Adoption Consistency & Drift Observation Governance.

## Demo countdown
First PHOENIX demo integration target: v21.225. After v21.205, 20 numbered modules remain through v21.225 inclusive.
