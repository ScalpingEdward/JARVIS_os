# PHOENIX v21.106 — Agent Recovery Certification & Return-to-Service Governance

## Purpose
v21.106 governs the final decision to certify a recovered agent as safe for return to service after incidents, disaster recovery or crisis exercises. It verifies restored service health, state/data integrity, dependency health, observability, capacity, business validation and human signoff without performing the return-to-service action itself.

## Core assurance
- Service-health verification
- State and data integrity
- Dependency health
- Post-recovery observability
- Error-budget and capacity readiness
- Business validation
- Rollback readiness
- Human signoff coverage
- Residual recovery risk

## Governed signals
`certified`, `recovery-alert`, `integrity-alert`, `observability-alert`, `business-alert`.

## API
- `GET /v1/agent-recovery-certification/status`
- `POST /v1/agent-recovery-certification/records`
- `GET /v1/agent-recovery-certification/records`
- `GET /v1/agent-recovery-certification/records/{record_id}`
- `POST /v1/agent-recovery-certification/records/{record_id}/actions`
- `GET /v1/agent-recovery-certification/audit`

## Safety boundary
This module is intelligence, verification and governance only. It does not return traffic to service, restart or replace runtimes, execute recovery or rollback, shift traffic, mutate infrastructure, permissions, credentials, models, memory, objectives, portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before active, monitoring or certified states. Unresolved recovery findings block approval. Critical integrity or business-validation failures can trigger a Risk Brain hard block.

## Integration
v21.105 evaluates crisis-simulation and recovery-exercise performance. v21.106 converts validated recovery evidence into a governed return-to-service certification decision while preserving the hard separation between governance and execution.
