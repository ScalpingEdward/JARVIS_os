# PHOENIX v21.145 — Baseline Impact Simulation & Change-Control Preview Governance

v21.145 evaluates a newly active reliability baseline in simulation before any downstream consumer may treat the changed baseline as trusted policy input.

## Flow

`Active Baseline → Simulation Scenarios → Ranking/Failover/Recovery Impact → Blast Radius → Human Review → Approved Preview`

## Simulated impact

The preview evaluates candidate score/rank movement, failover-trigger changes, recovery-readiness changes and maximum score delta. These signals are combined into a bounded blast-radius score and residual-risk estimate.

## Fail-closed controls

The preview is blocked when baseline admission is invalid, workspace binding fails, Risk Brain is blocked or simulated blast radius exceeds the configured threshold. Replay protection and deterministic evidence digests preserve auditability.

## Safety boundary

Simulation only. No route mutation, policy mutation, external network call, credential/permission expansion, fund movement, order submission or trading execution occurs.

## Next

v21.146 should add Baseline Consumer Eligibility & Controlled Rollout Governance, converting an approved simulation preview into a human-approved allow-list of downstream governance consumers with staged rollout metadata, without autonomous policy or routing mutation.
