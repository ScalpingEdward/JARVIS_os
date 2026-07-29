# PHOENIX v21.218 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance

## Purpose
Consumes human-approved `reconciliation-ready` evidence from v21.217 and governs a bounded, explicitly ordered recovery plan.

## Governance
- exact workspace and baseline lineage is retained;
- affected consumers must be unique and completely represented;
- healthy consumers are preserved and may not be targeted;
- recovery order must be contiguous and deterministic;
- blast-radius and residual-risk ceilings hold the plan for review;
- authorization is separate from per-step approval;
- step approvals must form an ordered prefix; out-of-order approval fails closed;
- all recovery steps must be approved before `recovery-ready`;
- duplicate ready sources and Risk Brain hard blocks fail closed;
- sequence and audit digests are deterministic.

## State machine
`reconciliation-ready` → `review-required` → authorization → `authorized` → ordered step approvals → `staged` → `recovery-ready`.

Invalid/replayed/out-of-order evidence → `blocked`. High blast radius or residual risk remains `review-required`.

## Boundary
This module authorizes and stages governance evidence only. It does not execute recovery, restart services, roll back live baselines, route orders, move funds, change permissions or actuate devices.

## Next
v21.219 — Recovery Reliability Recovery Receipt Reconciliation & Cross-Consumer Completion Governance.

## Demo countdown
After v21.218, 7 numbered modules remain through the v21.225 Demo 1 integration target.
