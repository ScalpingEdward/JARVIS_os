# PHOENIX v21.74 — Adaptive Strategy Allocation Intelligence Governance

## Purpose

PHOENIX v21.74 converts governed strategy observations into advisory allocation and lifecycle intelligence. It ranks strategies, evaluates regime fit, detects alpha decay, estimates risk-budget efficiency, and produces normalized target-weight recommendations.

The module is deliberately non-executing. It cannot activate strategies, rebalance portfolios, mutate allocations, submit orders, move funds, or access a broker execution path.

## Inputs

Each strategy observation may contain:

- expected and realized return
- volatility and downside deviation
- maximum drawdown
- win rate and profit factor
- alpha persistence
- current regime and regime-fit score
- average portfolio correlation
- liquidity score
- turnover rate
- current strategy weight
- confidence, freshness, and provenance

## Governed intelligence

The service calculates:

- strategy health score
- risk-adjusted score
- regime-fit score
- alpha-decay score
- portfolio strategy health
- regime alignment
- diversification quality
- alpha persistence
- risk-budget efficiency
- turnover requirement
- confidence score
- normalized advisory target weights
- maintain, retirement-candidate, and recovery-or-scale-candidate lifecycle signals

## Alerts

Governed flags include:

- strategy retirement candidate
- regime mismatch
- correlation alert
- turnover-limit breach
- strategy-weight-cap breach
- low confidence
- weak portfolio strategy health
- portfolio regime mismatch

## Workflow

Supported states:

`blocked`, `draft`, `evidence-ready`, `scored`, `policy-ready`, `review-required`, `approved`, `active`, `monitoring`, `stable`, `alpha-decay`, `regime-mismatch`, `correlation-alert`, `retirement-candidate`, `recovery-candidate`, `escalated`, `suspended`, `revoked`, and `archived`.

Human approval remains mandatory before a record can be treated as active governance intelligence. Operation IDs provide replay protection, source keys are unique within a workspace, and all actions are recorded in the audit trail.

## API

- `GET /v1/adaptive-strategy-allocation/status`
- `POST /v1/adaptive-strategy-allocation/records`
- `GET /v1/adaptive-strategy-allocation/records`
- `GET /v1/adaptive-strategy-allocation/records/{record_id}`
- `POST /v1/adaptive-strategy-allocation/records/{record_id}/actions`
- `GET /v1/adaptive-strategy-allocation/audit`

## Safety boundary

The status response explicitly reports:

- `allocation_mutation_enabled=false`
- `strategy_activation_enabled=false`
- `execution_enabled=false`
- `risk_brain_authority=hard-block`

Risk Brain remains authoritative and can hard-block approval, activation, or monitoring transitions.

## Integration

PHOENIX v21.62 through v21.73 provide governed macro, sentiment, flow, derivatives, cross-asset, liquidity, execution-quality, performance-attribution, portfolio-risk, capital-allocation, and scenario intelligence. v21.74 uses that context to produce adaptive strategy-allocation recommendations without crossing the execution boundary.
