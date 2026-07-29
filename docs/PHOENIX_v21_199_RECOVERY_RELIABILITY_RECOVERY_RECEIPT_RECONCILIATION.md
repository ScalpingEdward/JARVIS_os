# PHOENIX v21.199 — Recovery Reliability Recovery Receipt Reconciliation & Cross-Consumer Completion Governance

## Purpose
Consumes human-approved `recovery-ready` evidence from v21.198 and reconciles fresh recovery receipts across every expected affected consumer.

## Governance
- exact workspace and baseline ID/version/digest lineage;
- one receipt per expected consumer;
- unique receipt nonces and replay protection;
- receipt TTL/evidence-age validation;
- `recovered` and `healthy` are both mandatory;
- minimum recovery-quality threshold;
- missing, stale, unhealthy, unrecovered, low-quality or lineage-mismatched consumers remain `incomplete`;
- unexpected consumers, duplicate receipts/nonces, invalid admission, duplicate completed source or Risk Brain hard block fail closed;
- deterministic completion score and audit digest;
- final `completed` requires explicit human approval.

## State machine
`recovery-ready` → `review-required` → human approval → `completed`

Incomplete evidence → `incomplete`. Invalid/replayed/high-risk evidence → `blocked`.

## Boundary
This module reconciles evidence only. It does not restart consumers, execute recovery, mutate baselines, route orders, move funds, change permissions or actuate devices.

## Next
v21.200 — Recovery Reliability Stability Observation & Episode Closure Governance.
