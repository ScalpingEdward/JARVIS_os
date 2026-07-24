# PHOENIX v21.96 — Agent Production Certification & Release Gate Governance

## Purpose

PHOENIX v21.96 governs the final production-certification and release-gate decision for AI agents after promotion readiness has been established. It verifies that the target production environment, immutable artifacts, configuration, dependencies, required signoffs, release gates, observability, change window, runbooks and recovery controls are ready before a human may certify the candidate.

The module is governance and assurance only. It does not deploy, promote, shift traffic, restart runtimes, mutate release gates, execute rollback or run agent tools.

## Core controls

- production-environment parity
- artifact integrity
- configuration integrity
- dependency-lock assurance
- security signoff coverage
- risk signoff coverage
- operations signoff coverage
- release-gate coverage
- change-window readiness
- observability baseline readiness
- rollback and recovery readiness
- break-glass readiness
- runbook readiness
- blocking-finding detection
- environment-drift detection
- failed release-gate detection
- recovery-failure detection
- critical-agent Risk Brain hard blocks

## Lifecycle

- blocked
- draft
- evidence-ready
- assessed
- review-required
- approved
- active
- monitoring
- certified
- environment-alert
- signoff-alert
- release-gate-alert
- change-window-alert
- recovery-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-production-certification/status`
- `POST /v1/agent-production-certification/records`
- `GET /v1/agent-production-certification/records`
- `GET /v1/agent-production-certification/records/{record_id}`
- `POST /v1/agent-production-certification/records/{record_id}/actions`
- `GET /v1/agent-production-certification/audit`

## Approval and certification rules

Unresolved environment, signoff, release-gate, change-window, recovery, blocking-finding or residual-risk findings prevent approval. Production certification requires prior human approval. Critical agents can trigger a Risk Brain hard block when blocking findings remain unresolved, rollback/recovery has failed, release-gate checks repeatedly fail or residual risk becomes extreme.

## Safety boundary

The module explicitly reports:

- `deployment_execution_enabled=false`
- `release_gate_mutation_enabled=false`
- `traffic_shift_enabled=false`
- `automatic_rollback_enabled=false`
- `agent_execution_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

It cannot:

- deploy an agent
- promote a version
- shift production traffic
- mutate release-gate controls
- restart or replace a runtime
- execute rollback or recovery
- mutate model, memory, objective or permissions
- move funds
- mutate portfolios or routing
- submit or execute orders

## Integration

v21.96 sits above v21.95 Agent Promotion & Deployment Readiness Governance. v21.95 determines whether a candidate appears ready to be promoted. v21.96 independently certifies the exact production target and release-control evidence before a human can mark it certified. Promotion readiness cannot override Risk Brain, compliance, cybersecurity, model-risk, data-governance, operational-resilience or earlier agent-governance hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
