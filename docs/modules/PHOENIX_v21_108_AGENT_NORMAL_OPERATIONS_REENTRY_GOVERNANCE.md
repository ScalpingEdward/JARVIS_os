# PHOENIX v21.108 — Agent Normal Operations Re-entry & Hypercare Exit Governance

## Purpose
v21.108 governs the final transition from post-recovery hypercare back into normal operational governance. It verifies that stability is sustained, operational ownership is complete, residual risk is accepted and handoff evidence is sufficient before the hypercare phase can be formally exited.

## Core assurance
- Stabilization-window sufficiency
- Service-health, latency and error-rate stability
- State integrity and dependency health
- Business-KPI stability and error-budget posture
- Alert-noise quality and runbook currency
- Operational-owner readiness
- Hypercare-to-operations handoff completeness
- Residual-risk acceptance
- Reopened-incident, unresolved-finding and failed-handoff detection

## Governed signals
`normal-operations`, `stability-alert`, `governance-alert`, `ownership-alert`, `residual-risk-alert`.

## API
- `GET /v1/agent-normal-operations-reentry/status`
- `POST /v1/agent-normal-operations-reentry/records`
- `GET /v1/agent-normal-operations-reentry/records`
- `GET /v1/agent-normal-operations-reentry/records/{record_id}`
- `POST /v1/agent-normal-operations-reentry/records/{record_id}/actions`
- `GET /v1/agent-normal-operations-reentry/audit`

## Safety boundary
This module is intelligence, verification and governance only. It does not execute hypercare exit, shift traffic, restart or replace runtimes, remediate, roll back, mutate permissions, credentials, infrastructure, models, memory, objectives, portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before governed active, monitoring or normal-operations states. Unresolved findings block approval. Critical reopened incidents, failed handoffs, unresolved high findings or extreme residual risk can trigger a Risk Brain hard block.

## Integration
v21.107 verifies stability during the post-recovery hypercare window. v21.108 closes that lifecycle by governing whether the agent is ready to leave hypercare and return to standard operational governance without performing the operational cutover itself.
