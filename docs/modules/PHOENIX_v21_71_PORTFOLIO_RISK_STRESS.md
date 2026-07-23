# PHOENIX v21.71 — Portfolio Risk & Stress Intelligence Governance

## Purpose

This module converts governed portfolio exposure observations into advisory risk decomposition and stress intelligence. It does not place orders, rebalance portfolios, move funds or mutate allocations.

## Core intelligence

- concentration risk
- expected shortfall
- scenario stress loss
- drawdown pressure
- liquidity risk
- correlation-cluster risk
- portfolio risk resilience
- confidence and freshness weighting

## Governed alerts

- concentration-alert
- stress-breach
- drawdown-alert
- liquidity-risk-high
- correlation-cluster-risk
- low-confidence

## API

- `GET /v1/portfolio-risk-stress/status`
- `POST /v1/portfolio-risk-stress/records`
- `GET /v1/portfolio-risk-stress/records`
- `GET /v1/portfolio-risk-stress/records/{record_id}`
- `POST /v1/portfolio-risk-stress/records/{record_id}/actions`
- `GET /v1/portfolio-risk-stress/audit`

## Governance controls

- mandatory human approval before activation
- Risk Brain hard-block authority
- workspace isolation
- duplicate source-key protection
- idempotent operation receipts
- complete audit trail
- versioned lifecycle transitions

## Safety boundary

The status endpoint explicitly reports:

- `allocation_mutation_enabled=false`
- `execution_enabled=false`

The module is intelligence-only. Downstream systems must independently enforce execution and allocation controls.

## Integration

PHOENIX v21.62–v21.70 governed outputs can contextualize macro regimes, alternative data, sentiment, institutional flows, derivatives, cross-asset conditions, liquidity, execution costs and realized attribution. v21.71 converts current exposure data into controlled portfolio risk and stress intelligence.
