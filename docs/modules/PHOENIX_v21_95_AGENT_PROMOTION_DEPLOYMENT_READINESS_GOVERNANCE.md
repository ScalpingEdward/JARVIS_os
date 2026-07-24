# PHOENIX v21.95 — Agent Promotion & Deployment Readiness Governance

## Purpose

PHOENIX v21.95 governs whether an AI-agent candidate is sufficiently validated, observable, compatible and recoverable to be considered promotion-ready. The module is advisory and governance-only. It does not deploy agents, shift traffic, mutate runtime state or execute automatic rollback.

## Core controls

- validation coverage
- regression coverage
- safety validation
- compatibility assurance
- dependency readiness
- observability readiness
- rollback readiness
- canary readiness
- change traceability
- human-review coverage
- blocking-finding detection
- regression-failure detection
- rollback-failure detection
- unresolved-dependency detection
- observability-gap detection
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
- promotion-ready
- validation-gap
- compatibility-alert
- observability-alert
- rollback-alert
- release-risk-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-promotion-readiness/status`
- `POST /v1/agent-promotion-readiness/records`
- `GET /v1/agent-promotion-readiness/records`
- `GET /v1/agent-promotion-readiness/records/{record_id}`
- `POST /v1/agent-promotion-readiness/records/{record_id}/actions`
- `GET /v1/agent-promotion-readiness/audit`

## Approval rules

Unresolved validation, safety, compatibility, dependency, observability, rollback or residual-risk findings block approval. Activation requires a prior human approval state. Business-critical candidates with blocking findings, rollback failures, severe safety weakness or extreme residual risk receive a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `deployment_execution_enabled=false`
- `automatic_promotion_enabled=false`
- `traffic_shift_enabled=false`
- `automatic_rollback_enabled=false`
- `agent_execution_enabled=false`
- `execution_enabled=false`

It cannot:

- deploy or promote an agent
- shift production traffic
- restart or replace agent runtimes
- execute rollback
- mutate model, memory, policy or objectives
- change credentials or permissions
- mutate portfolios or routing
- move funds
- submit or execute orders

## Integration

v21.95 sits above v21.94 Agent Learning & Adaptation Governance. v21.94 can determine whether an adaptation proposal is sufficiently supported; v21.95 independently determines whether a resulting candidate is operationally ready for promotion. Promotion readiness cannot override Risk Brain, compliance, cybersecurity, model-risk, data-governance, runtime-supervision, objective-alignment or release-governance hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
