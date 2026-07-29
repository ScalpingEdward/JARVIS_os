# PHOENIX v21.208 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance

## Purpose
Consumes human-approved `reconciliation-ready` evidence from v21.207 and governs a bounded, explicitly ordered recovery plan.

## Governance
- exact workspace and baseline lineage is retained;
- healthy consumers are preserved and may not be targeted;
- every affected consumer must appear exactly once in the recovery sequence;
- recovery order must be contiguous and deterministic;
- blast-radius and residual-risk ceilings hold the plan for review;
- authorization is separate from per-step approval;
- step approvals must form an ordered prefix; out-of-order approval fails closed;
- all steps must be approved before `recovery-ready`;
- duplicate ready sources and Risk Brain hard blocks fail closed;
- sequence and audit digests are deterministic.

## State machine
`reconciliation-ready` → `review-required` → authorization → `authorized` → ordered step approvals → `staged` → `recovery-ready`.

Invalid/replayed/out-of-order/high-risk governance evidence → `blocked` or remains `review-required` as appropriate.

## Boundary
This module authorizes and stages evidence only. It does not execute recovery, restart services, roll back a live baseline, route orders, move funds, change permissions or actuate devices.

## Next
v21.209 — Recovery Reliability Recovery Receipt Reconciliation & Cross-Consumer Completion Governance.

## Demo countdown
After v21.208, 17 numbered modules remain through the v21.225 Demo 1 integration target.
