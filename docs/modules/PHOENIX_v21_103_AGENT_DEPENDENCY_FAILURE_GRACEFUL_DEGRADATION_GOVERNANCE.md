# PHOENIX v21.103 — Agent Dependency Failure & Graceful Degradation Governance

## Purpose
v21.103 extends capacity and stress assurance into dependency-failure governance. It evaluates whether an agent can preserve safe behavior, data integrity and recoverability when a critical upstream or downstream dependency is degraded or unavailable.

## Core assurance
- Dependency criticality and redundancy coverage
- Failover readiness and fallback quality
- Graceful-degradation quality
- Data-integrity preservation and state consistency
- Recovery readiness and recovery-point assurance
- Observability and human-override readiness
- Single-point-of-failure detection
- Failed failover/recovery checks
- Degradation and integrity violation detection
- Aggregate dependency-failure assurance and residual risk

## Governed signals
`verified`, `dependency-alert`, `failover-alert`, `degradation-alert`, `recovery-alert`, `data-integrity-alert`.

## API
- `GET /v1/agent-dependency-failure/status`
- `POST /v1/agent-dependency-failure/records`
- `GET /v1/agent-dependency-failure/records`
- `GET /v1/agent-dependency-failure/records/{record_id}`
- `POST /v1/agent-dependency-failure/records/{record_id}/actions`
- `GET /v1/agent-dependency-failure/audit`

## Safety boundary
This module is intelligence, verification and governance only. It does not inject faults, trigger failover, switch fallbacks, recover or restart runtimes, shift traffic, mutate infrastructure, permissions, credentials, models, memory, objectives, portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before governed active, monitoring or verified states. Unresolved dependency-failure findings block approval. Critical dependencies with single points of failure, failed failover or integrity violations can trigger a Risk Brain hard block.

## Integration
v21.102 verifies that the agent has sufficient operating headroom. v21.103 verifies that safe service behavior remains governable when individual dependencies fail, degrade or become inconsistent.
