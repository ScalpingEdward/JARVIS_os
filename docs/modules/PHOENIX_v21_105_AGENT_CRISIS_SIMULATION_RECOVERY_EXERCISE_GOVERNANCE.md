# PHOENIX v21.105 — Agent Crisis Simulation & Recovery Exercise Governance

## Purpose
v21.105 extends disaster-recovery readiness from static controls into governed crisis exercises. It verifies that incident command, communications, recovery sequencing, runbooks and recovery objectives remain effective under realistic simulated crisis conditions without executing faults or recovery actions itself.

## Core assurance
- Scenario coverage and severity realism
- Incident-command readiness
- Decision timing quality
- Stakeholder communication readiness
- Recovery-sequence quality
- RTO and RPO attainment
- Dependency coordination
- Runbook effectiveness
- Evidence capture
- Lessons-learned quality
- Residual exercise risk and Risk Brain escalation

## Governed signals
`verified`, `scenario-alert`, `command-alert`, `recovery-alert`, `communication-alert`, `lessons-alert`.

## API
- `GET /v1/agent-crisis-exercises/status`
- `POST /v1/agent-crisis-exercises/records`
- `GET /v1/agent-crisis-exercises/records`
- `GET /v1/agent-crisis-exercises/records/{record_id}`
- `POST /v1/agent-crisis-exercises/records/{record_id}/actions`
- `GET /v1/agent-crisis-exercises/audit`

## Safety boundary
This module is intelligence, verification and governance only. It does not execute crisis scenarios, inject faults, fail over, recover or restart runtimes, shift traffic, mutate infrastructure, credentials, permissions, models, memory, objectives, portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before governed active, monitoring or verified states. Unresolved exercise findings block approval. Critical command or recovery failures can trigger a Risk Brain hard block.

## Integration
v21.104 verifies disaster-recovery and service-continuity controls. v21.105 verifies organizational and technical response quality under simulated crisis conditions, closing the gap between documented readiness and exercised readiness.
