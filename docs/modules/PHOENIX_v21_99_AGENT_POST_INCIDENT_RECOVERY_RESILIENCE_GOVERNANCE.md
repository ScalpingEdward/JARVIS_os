# PHOENIX v21.99 — Agent Post-Incident Recovery & Resilience Governance

## Purpose
v21.99 governs what happens after an incident has been contained and service is restored. It verifies that restoration is stable, root cause is understood, corrective and preventive controls are closed, resilience tests pass, and lessons learned are operationalized before an agent is considered resilient again.

## Core assurance
- Service restoration quality
- Stability and regression validation
- Root-cause confidence
- Corrective action coverage
- Preventive control coverage
- Resilience test coverage
- Observability and runbook improvements
- Lessons-learned closure
- Owner accountability
- Repeat-failure detection
- Residual resilience risk

## Governed lifecycle signals
`resilient`, `recovery-gap`, `control-gap`, `recurrence-alert`, `validation-alert`, `lessons-alert`.

## API
- `GET /v1/agent-post-incident-recovery/status`
- `POST /v1/agent-post-incident-recovery/records`
- `GET /v1/agent-post-incident-recovery/records`
- `GET /v1/agent-post-incident-recovery/records/{record_id}`
- `POST /v1/agent-post-incident-recovery/records/{record_id}/actions`
- `GET /v1/agent-post-incident-recovery/audit`

## Safety boundary
Governance and assurance only. No automatic remediation, control mutation, redeployment, runtime restart/replacement, traffic shift, model/memory/objective mutation, permission or credential mutation, infrastructure mutation, portfolio or routing mutation, fund movement, order submission or trading execution.

Human approval is mandatory before active, monitoring or resilient states. Open findings block approval. Critical agents with recurring failures, failed resilience tests or extreme residual risk can trigger a Risk Brain hard block.

## Integration
v21.98 governs active incident response. v21.99 verifies durable recovery and resilience improvements after the incident, closing the loop from detection through containment to verified prevention of recurrence.
