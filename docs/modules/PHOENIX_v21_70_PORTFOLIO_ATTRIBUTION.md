# PHOENIX v21.70 — Portfolio Performance Attribution Intelligence Governance

## Purpose

This module evaluates portfolio and strategy performance relative to governed benchmarks. It separates active return into allocation and selection effects, measures transaction-cost drag, risk efficiency, drawdown resilience, alpha persistence and evidence confidence.

## Governance boundary

The module is advisory only. It cannot place orders, move funds or mutate portfolio allocations. Activation requires human approval and remains subject to Risk Brain hard blocks.

## Inputs

Each observation contains a portfolio sleeve, asset class, strategy, portfolio return, benchmark return, weight, active risk, drawdown, turnover, transaction costs, confidence, freshness and provenance.

## Scores

- total and benchmark return
- active return
- allocation effect
- selection effect
- transaction-cost drag
- risk efficiency
- drawdown resilience
- alpha persistence
- confidence

## Governed alerts

- alpha decay
- risk drift
- benchmark divergence
- drawdown stress
- low confidence

## API

- `GET /v1/portfolio-attribution/status`
- `POST /v1/portfolio-attribution/records`
- `GET /v1/portfolio-attribution/records`
- `GET /v1/portfolio-attribution/records/{record_id}`
- `POST /v1/portfolio-attribution/records/{record_id}/actions`
- `GET /v1/portfolio-attribution/audit`

## Controls

Workspace isolation, duplicate source-key protection, idempotent operation receipts, immutable audit events, human approval and Risk Brain hard-block authority are mandatory.

## Integration

Outputs from PHOENIX v21.62 through v21.69 can contextualize macro regime, alternative data, sentiment, institutional flow, derivatives positioning, cross-asset behavior, liquidity and observed transaction costs. v21.70 converts those governed inputs into post-trade portfolio attribution and decision intelligence.
