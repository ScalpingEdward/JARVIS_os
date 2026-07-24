# PHOENIX v21.99 — Agent Post-Incident Root Cause & Corrective Action Governance

## Purpose
v21.99 governs the post-incident learning and corrective-action phase after v21.98 Incident Response Governance. It verifies whether root causes are adequately evidenced, whether corrective and preventive actions are owned and reviewable, and whether recurrence risk is being reduced without executing remediation automatically.

## Core assurance
- Root-cause confidence
- Evidence completeness
- Causal-chain and contributing-factor coverage
- Corrective-action quality
- Preventive-action quality
- Action-owner accountability and due-date readiness
- Verification-plan quality
- Recurrence-prevention assurance
- Cross-agent/systemic impact review
- Repeat-incident detection
- Residual-risk and Risk Brain escalation

## Governed lifecycle signals
`verified`, `root-cause-alert`, `corrective-action-alert`, `preventive-action-alert`, `owner-alert`, `recurrence-alert`.

## API
- `GET /v1/agent-post-incident-rca/status`
- `POST /v1/agent-post-incident-rca/records`
- `GET /v1/agent-post-incident-rca/records`
- `GET /v1/agent-post-incident-rca/records/{record_id}`
- `POST /v1/agent-post-incident-rca/records/{record_id}/actions`
- `GET /v1/agent-post-incident-rca/audit`

## Safety boundary
This module is intelligence and governance only. It does not apply corrective actions, mutate code/configuration, deploy changes, restart runtimes, alter permissions or credentials, mutate infrastructure, portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before governed active/monitoring/verified states. Unresolved RCA/CAPA findings block approval. Critical repeated incidents, unresolved root causes, failed verification or extreme residual risk can trigger a Risk Brain hard block.

## Integration
v21.98 governs incident handling. v21.99 governs the evidence-backed learning and remediation plan that follows the incident. Any actual implementation remains downstream and separately permissioned through change, release and production-certification controls.
