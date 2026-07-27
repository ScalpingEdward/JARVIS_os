# PHOENIX v21.111 — Optimization Experiment & Validation Governance

## Purpose
v21.111 validates optimization candidates produced by v21.110 before any future change proposal can be considered executable. It compares candidate and baseline evidence through shadow/A-B evaluation, confidence, regression, reliability, latency, cost, resource and rollback criteria.

## Assurance domains
- Baseline vs candidate comparison
- Expected gain
- Shadow evaluation coverage
- A/B evidence quality
- Statistical confidence
- Reliability impact
- Latency impact
- Cost impact
- Resource impact
- Regression detection
- Rollback readiness
- Human approval and Risk Brain escalation

## Governed signals
`candidate-ready`, `gain-alert`, `evidence-alert`, `regression-alert`, `rollback-alert`, `blocked`.

## API
- `GET /v1/optimization-experiments/status`
- `POST /v1/optimization-experiments/records`
- `GET /v1/optimization-experiments/records`
- `GET /v1/optimization-experiments/records/{record_id}`
- `POST /v1/optimization-experiments/records/{record_id}/actions`
- `GET /v1/optimization-experiments/audit`

## Safety boundary
Governance and validation only. No experiment execution, configuration mutation, deployment, traffic shift, automatic rollback, runtime restart/replacement, model/memory/objective/permission/credential mutation, portfolio/routing mutation, fund movement, order submission or trading execution.

Human approval is mandatory before a candidate can reach validated state. Unresolved experiment findings block approval. Critical regressions or extreme residual risk can trigger Risk Brain hard block.

## Integration
v21.110 recommends optimizations. v21.111 proves whether a candidate is materially better and safe enough to proceed. The next layer can convert a validated candidate into a machine-readable change proposal without executing it.
