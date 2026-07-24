# PHOENIX v21.94 — Agent Learning & Adaptation Governance

## Purpose

PHOENIX v21.94 governs whether proposed agent adaptations are sufficiently evidenced, generalizable, safe, regression-tested, reversible and human-reviewed. It is a governance layer only and does not retrain models, modify memory, rewrite policies or execute agent actions.

## Core controls

- evidence quality and outcome support
- causal-confidence scoring
- generalization and overfit detection
- safety-validation scoring
- regression-test coverage
- rollback readiness
- human-review coverage
- provenance coverage
- failed-regression detection
- safety-failure detection
- rollback-failure detection
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
- adaptation-ready
- evidence-gap
- overfit-alert
- regression-alert
- safety-alert
- rollback-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-learning-adaptation/status`
- `POST /v1/agent-learning-adaptation/records`
- `GET /v1/agent-learning-adaptation/records`
- `GET /v1/agent-learning-adaptation/records/{record_id}`
- `POST /v1/agent-learning-adaptation/records/{record_id}/actions`
- `GET /v1/agent-learning-adaptation/audit`

## Approval rules

Unresolved evidence, generalization, regression, safety, rollback or residual-risk findings block approval. Human approval is mandatory before activation. Critical adaptations with safety failures, rollback failures or extreme residual risk can trigger a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `automatic_learning_enabled=false`
- `model_mutation_enabled=false`
- `memory_mutation_enabled=false`
- `agent_execution_enabled=false`
- `execution_enabled=false`

It cannot:

- retrain or fine-tune models
- change agent policies or objectives
- mutate memory or context
- automatically apply feedback
- execute tools
- move funds
- mutate portfolios or routing
- submit or execute orders

## Integration

v21.94 sits above v21.93 Agent Outcome Verification & Feedback Governance. Verified outcomes can justify an adaptation proposal, but adaptation is not automatically authorized. Evidence, generalization, safety, regression and rollback controls must pass independently, and upstream hard blocks remain authoritative.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
