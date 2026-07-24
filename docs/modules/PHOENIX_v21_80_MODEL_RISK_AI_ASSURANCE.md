# PHOENIX v21.80 — Model Risk & AI Assurance Governance

## Purpose

PHOENIX v21.80 adds an independent model-risk and AI-assurance layer above institutional compliance governance. It evaluates whether critical analytical, predictive and decision-support models remain validated, stable, explainable, fair, data-governed and operationally resilient.

The module is advisory and governance-only. It cannot change models, deploy versions, alter portfolios, route orders or execute trades.

## Core assessments

- Independent validation coverage
- Performance stability and calibration
- Robustness under adverse conditions
- Explainability and human-oversight coverage
- Fairness and bias controls
- Input-data quality and provenance
- Concept and performance drift
- Fallback and rollback readiness
- Open validation findings and incident history
- Business criticality and residual model risk

## Governed signals

- assured
- validation-required
- drift-alert
- bias-alert
- explainability-gap
- data-quality-alert
- validation-failure
- risk-brain-hard-block

## Lifecycle

- blocked
- draft
- evidence-ready
- assessed
- validation-required
- review-required
- approved
- active
- monitoring
- assured
- drift-alert
- bias-alert
- explainability-gap
- data-quality-alert
- validation-failure
- escalated
- suspended
- revoked
- archived

## API

- `GET /v1/model-risk-ai-assurance/status`
- `POST /v1/model-risk-ai-assurance/records`
- `GET /v1/model-risk-ai-assurance/records`
- `GET /v1/model-risk-ai-assurance/records/{record_id}`
- `POST /v1/model-risk-ai-assurance/records/{record_id}/actions`
- `GET /v1/model-risk-ai-assurance/audit`

## Governance controls

- Human approval before activation
- Unresolved model-risk findings block approval
- Critical high-risk models trigger a Risk Brain hard block
- Workspace isolation
- Duplicate source-key protection
- Operation-receipt replay protection
- Complete audit trail
- Evidence provenance and freshness weighting

## Safety boundary

The status endpoint explicitly reports:

- `model_mutation_enabled=false`
- `deployment_mutation_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

The module performs no model replacement, retraining, deployment, portfolio mutation, capital allocation, routing mutation, fund movement, order submission or execution.

## Integration

v21.80 consumes governance context from v21.79 and independently validates the models that power PHOENIX intelligence, risk, allocation, broker, infrastructure and committee layers. Compliance approval cannot override failed model validation, and model assurance cannot override Risk Brain or compliance hard blocks.
