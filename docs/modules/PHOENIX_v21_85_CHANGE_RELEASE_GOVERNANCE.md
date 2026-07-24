# PHOENIX v21.85 — Change & Release Governance

PHOENIX v21.85 introduces an institutional change-management and release-assurance layer above third-party and supply-chain risk governance.

## Objective

The module evaluates software, configuration, model-supporting and infrastructure-supporting changes before they may be considered release-ready. It remains governance-only and cannot deploy, roll back or execute trading activity.

## Assessment dimensions

- test coverage
- regression coverage
- rollback readiness
- peer-review coverage
- segregation of duties
- security-review coverage
- dependency-impact knowledge
- observability readiness
- canary readiness
- deployment rehearsal
- blocking findings
- recent failed releases
- change criticality
- evidence confidence and freshness

## Aggregate scores

The service produces:

- test assurance
- rollback resilience
- review integrity
- security assurance
- dependency readiness
- observability readiness
- deployment readiness
- aggregate release assurance
- aggregate residual change risk
- evidence confidence

## Governed lifecycle signals

Per-change dispositions can resolve to:

- release-ready
- test-gap
- rollback-gap
- segregation-alert
- security-alert
- observability-gap
- change-risk-alert

The record lifecycle also supports blocked, draft, evidence-ready, assessed, review-required, approved, active, monitoring, escalated, suspended, revoked and archived states.

## Required actions

Depending on findings the module can require:

- expanded test and regression coverage
- proven rollback and recovery plan
- independent change review
- security impact review
- release observability and alerting definition
- Change Advisory Board review
- Risk Brain hard block for critical unsafe changes

## Approval rules

Human approval is mandatory before activation. Any unresolved change-governance finding blocks approval. Critical changes with blocking findings, severe residual risk or critically weak rollback readiness can trigger a Risk Brain hard block.

## Replay and isolation controls

- operation IDs are unique per workspace
- duplicate operations are rejected
- source keys are unique per workspace
- records cannot be read across workspace boundaries
- all lifecycle actions are appended to an audit trail

## API

- `GET /v1/change-release-governance/status`
- `POST /v1/change-release-governance/records`
- `GET /v1/change-release-governance/records`
- `GET /v1/change-release-governance/records/{record_id}`
- `POST /v1/change-release-governance/records/{record_id}/actions`
- `GET /v1/change-release-governance/audit`

## Safety boundary

The module is advisory and governance-only.

It does **not**:

- deploy releases
- modify deployment configuration
- trigger rollback
- mutate infrastructure
- change portfolios
- change routing
- move funds
- submit orders
- execute trades

The status endpoint therefore reports:

- `deployment_mutation_enabled=false`
- `release_execution_enabled=false`
- `rollback_execution_enabled=false`
- `execution_enabled=false`

## Integration

v21.85 extends v21.84 by governing how changes to PHOENIX-controlled systems are assessed before release. Strong third-party, cyber, data, model and operational controls cannot compensate for unsafe change practices. Change approval cannot override upstream compliance, model-risk, operational-resilience, cybersecurity, third-party or Risk Brain hard blocks.
