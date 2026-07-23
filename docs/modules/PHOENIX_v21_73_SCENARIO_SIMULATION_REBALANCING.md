# PHOENIX v21.73 — Scenario Simulation & Rebalancing Intelligence Governance

## Purpose

This module converts governed portfolio exposures, target weights and explicit market shocks into advisory scenario-loss, resilience and rebalancing-pressure intelligence. It never mutates allocations and never submits orders.

## Capabilities

- Multi-factor scenario shock modeling
- Probability-weighted and tail-loss estimates
- Liquidity and volatility multiplier stress
- Correlation-shift stress
- Turnover requirement measurement
- Portfolio, liquidity and correlation resilience scoring
- Governed advisory target-weight recommendations
- Scenario-breach, rebalancing-pressure and resilience-decay detection
- Workspace isolation and duplicate source-key protection
- Human approval, replay protection and full audit trail
- Risk Brain hard-block authority

## API

- `GET /v1/scenario-simulation/status`
- `POST /v1/scenario-simulation/records`
- `GET /v1/scenario-simulation/records`
- `GET /v1/scenario-simulation/records/{record_id}`
- `POST /v1/scenario-simulation/records/{record_id}/actions`
- `GET /v1/scenario-simulation/audit`

## Governed states

`blocked`, `draft`, `evidence-ready`, `scored`, `policy-ready`, `review-required`, `approved`, `active`, `monitoring`, `stable`, `scenario-breach`, `rebalance-pressure`, `resilience-decay`, `escalated`, `suspended`, `revoked`, `archived`.

## Safety boundary

- Advisory intelligence only
- No portfolio rebalancing
- No allocation mutation
- No order submission or cancellation
- No fund movement or broker execution
- Human approval is mandatory before activation
- Risk Brain hard blocks remain authoritative
- Status exposes `allocation_mutation_enabled=false` and `execution_enabled=false`

## Integration

PHOENIX v21.62 through v21.72 governed outputs can provide macro, sentiment, flow, derivatives, cross-asset, liquidity, execution-quality, attribution, portfolio-risk and capital-allocation context. v21.73 applies explicit shocks to that context and produces controlled scenario and rebalancing recommendations.

## Validation

Tests cover scoring, normalized recommendations, duplicate protection, workspace isolation, approval, operation replay, Risk Brain blocking and the non-execution safety boundary.
