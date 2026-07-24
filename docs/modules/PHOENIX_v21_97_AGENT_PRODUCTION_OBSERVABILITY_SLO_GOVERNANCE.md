# PHOENIX v21.97 — Agent Production Observability & SLO Governance

## Purpose

PHOENIX v21.97 governs post-certification production health for AI agents. It verifies whether certified agents remain observable, within service-level objectives, inside error-budget limits, operationally supportable, and free from material behavioral or decision drift.

This module is governance and assurance only. It does not restart agents, scale infrastructure, shift traffic, roll back deployments, mutate models or execute trading activity.

## Core controls

- availability SLO attainment
- latency SLO attainment
- error-rate SLO attainment
- telemetry coverage
- distributed trace coverage
- log and metric quality
- alert precision
- incident-detection readiness
- human on-call readiness
- runbook coverage
- error-budget remaining
- behavioral drift detection
- decision drift detection
- critical and unresolved incident detection
- false-negative alert detection
- Risk Brain hard-block escalation

## Lifecycle

- blocked
- draft
- evidence-ready
- assessed
- review-required
- approved
- active
- monitoring
- healthy
- slo-alert
- error-budget-alert
- telemetry-alert
- incident-alert
- drift-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-production-observability/status`
- `POST /v1/agent-production-observability/records`
- `GET /v1/agent-production-observability/records`
- `GET /v1/agent-production-observability/records/{record_id}`
- `POST /v1/agent-production-observability/records/{record_id}/actions`
- `GET /v1/agent-production-observability/audit`

## Approval rules

Records with unresolved SLO, error-budget, telemetry, incident, drift or residual-risk findings cannot be approved. A healthy production lifecycle requires prior human approval. Critical production agents can receive a Risk Brain hard block when severe incidents, exhausted error budgets, extreme SLO degradation, material drift or extreme residual risk are observed.

## Safety boundary

The module explicitly reports:

- `automatic_remediation_enabled=false`
- `automatic_scaling_enabled=false`
- `traffic_shift_enabled=false`
- `automatic_rollback_enabled=false`
- `agent_execution_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

It cannot:

- restart or replace production agents
- autoscale runtime infrastructure
- change routing or shift production traffic
- automatically roll back a release
- mutate model, memory, objective or policy state
- grant or revoke permissions
- move funds
- mutate portfolios
- submit or execute orders

## Integration

v21.97 sits directly above v21.96 Agent Production Certification & Release Gate Governance. v21.96 proves that a specific candidate is ready to enter production; v21.97 verifies that the production system continues to satisfy SLOs, observability, incident-response, error-budget and drift requirements after release.

Production observability governance cannot override Agent Authorization, Runtime Supervision, Memory/Context Provenance, Objective Alignment, Decision Accountability, Outcome Verification, Learning/Adaptation, Production Certification, Risk Brain, compliance, cybersecurity, model-risk or data-governance hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
