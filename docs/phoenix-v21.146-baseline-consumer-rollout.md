# PHOENIX v21.146 — Baseline Consumer Eligibility & Controlled Rollout Governance

v21.146 turns a human-approved v21.145 simulation preview into a bounded allow-list of downstream governance consumers and staged rollout metadata.

## Flow

`Active Baseline → Approved Simulation Preview → Consumer Eligibility → Human Approval → Staged Rollout → Active`

## Eligible consumers

- adapter-selection
- worker-selection
- dispatch-planning
- failover-health
- recovery-readiness

Unsupported consumers fail closed. The rollout also blocks when the preview is not approved, workspace binding fails, blast radius or residual risk exceed ceilings, or Risk Brain is blocked.

## Stage governance

Stage advancement requires explicit human approval at every transition. The module stores stage metadata and deterministic digests but does not mutate downstream routing or policies itself.

## Safety boundary

No external network execution, routing mutation, policy mutation, credential/permission change, fund movement, order submission, or trading execution is performed.

## Next

v21.147 should add Baseline Consumer Adoption Receipt & Drift Monitoring Governance, requiring downstream consumers to acknowledge the approved baseline version and reporting drift/mismatch without autonomous policy correction.
