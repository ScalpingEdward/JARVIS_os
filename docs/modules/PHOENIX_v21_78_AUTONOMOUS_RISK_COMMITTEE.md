# PHOENIX v21.78 — Autonomous Risk Committee Governance

## Purpose

PHOENIX v21.78 introduces a governed committee layer above the real-time Portfolio AI Brain. It aggregates independent domain assessments, checks quorum, calculates weighted support and opposition, recognizes veto-domain objections, and produces an auditable advisory decision.

The module does not modify portfolios, limits, allocations, routing, infrastructure or orders.

## Committee inputs

Each member assessment contains:

- member and domain identity
- support, caution, oppose or abstain stance
- confidence and risk severity
- written rationale
- evidence references

Typical domains include Risk Brain, portfolio risk, liquidity, strategy, execution, infrastructure, compliance and capital allocation.

## Deliberation

The committee calculates:

- quorum participation
- confidence-weighted approval ratio
- confidence-weighted opposition ratio
- weighted risk severity
- veto-domain status
- required review actions

Possible advisory decisions include:

- approve advisory context
- hold
- escalate
- capital-preservation review

A high-confidence objection from a configured veto domain prevents approval. Human approval remains mandatory before activation.

## Governed lifecycle

`evidence-ready → deliberating → review-required → approved → active → monitoring`

Additional states cover risk warnings, limit review, capital preservation, infrastructure holds, escalation, suspension, revocation and archival.

## API

- `GET /v1/autonomous-risk-committee/status`
- `POST /v1/autonomous-risk-committee/records`
- `GET /v1/autonomous-risk-committee/records`
- `GET /v1/autonomous-risk-committee/records/{record_id}`
- `POST /v1/autonomous-risk-committee/records/{record_id}/actions`
- `GET /v1/autonomous-risk-committee/audit`

All record and audit endpoints are workspace-scoped. Source keys are unique per workspace and operation IDs are replay-protected.

## Safety boundary

The status contract explicitly reports:

- `advisory_only=true`
- `portfolio_mutation_enabled=false`
- `allocation_mutation_enabled=false`
- `limit_mutation_enabled=false`
- `execution_enabled=false`
- `human_approval_required=true`
- `risk_brain_authoritative=true`

The Risk Brain remains authoritative and cannot be overruled by committee synthesis.
