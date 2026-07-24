# PHOENIX v21.98 — Agent Production Incident Response Governance

## Purpose
v21.98 governs the response lifecycle when a production agent experiences a material incident. It converts detection from v21.97 into structured severity, triage, containment, recovery, communication, evidence and postmortem assurance without performing operational remediation.

## Core assurance
- Detection and triage quality
- Severity and critical-impact assessment
- Containment readiness
- Recovery and rollback readiness
- Human incident-command coverage
- Stakeholder communication readiness
- Evidence preservation
- Postmortem readiness
- Lessons-learned traceability and repeat-incident detection
- Residual incident risk and Risk Brain escalation

## Governed lifecycle signals
`contained`, `severity-alert`, `containment-alert`, `recovery-alert`, `communication-alert`, `postmortem-alert`.

## API
- `GET /v1/agent-production-incidents/status`
- `POST /v1/agent-production-incidents/records`
- `GET /v1/agent-production-incidents/records`
- `GET /v1/agent-production-incidents/records/{record_id}`
- `POST /v1/agent-production-incidents/records/{record_id}/actions`
- `GET /v1/agent-production-incidents/audit`

## Safety boundary
This module is intelligence and governance only. It does not contain agents, restart or replace runtimes, recover services, execute rollback, autoscale, shift traffic, mutate infrastructure, alter models/memory/objectives/permissions/credentials, mutate portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before governed active/monitoring/contained states. Unresolved findings block approval. Critical business-impact incidents with failed containment/recovery or extreme residual risk can trigger a Risk Brain hard block.

## Integration
v21.97 determines whether production behavior violates SLO/observability requirements. v21.98 governs what must be reviewed and evidenced once an incident exists. Future execution/remediation components remain downstream and separately permissioned.
