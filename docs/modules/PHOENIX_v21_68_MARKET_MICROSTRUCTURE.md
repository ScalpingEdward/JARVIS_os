# PHOENIX v21.68 — Market Microstructure & Liquidity Intelligence Governance

## Purpose

This module converts venue-level order-book and execution observations into governed liquidity intelligence. It is strictly analytical: it cannot place trades, mutate allocations, transfer funds or bypass the Risk Brain.

## Coverage

- quoted spread and spread stress
- displayed depth and depth resilience
- bid/ask order-flow imbalance
- venue fragmentation and price dispersion
- cancellation intensity
- venue latency
- execution-quality degradation
- liquidity confidence

## Governed states

`blocked`, `draft`, `evidence-ready`, `scored`, `policy-ready`, `review-required`, `approved`, `active`, `monitoring`, `stable`, `liquidity-shift`, `order-flow-imbalance`, `fragmentation-alert`, `escalated`, `suspended`, `revoked`, `archived`.

## API

- `GET /v1/market-microstructure/status`
- `POST /v1/market-microstructure/records`
- `GET /v1/market-microstructure/records`
- `GET /v1/market-microstructure/records/{record_id}`
- `POST /v1/market-microstructure/records/{record_id}/actions`
- `GET /v1/market-microstructure/audit`

All record endpoints require `X-Workspace-ID`. Source keys are unique per workspace and every state-changing action requires a single-use operation receipt.

## Safety controls

- human approval before activation
- authoritative Risk Brain hard block
- workspace isolation
- replay protection
- duplicate-source protection
- immutable-style audit events
- no broker or execution adapter

## Upstream context

The module may consume governed outputs from macro regimes, alternative data, news sentiment, institutional flow, options gamma and cross-asset intelligence.

## Downstream consumers

Governed scores may inform portfolio orchestration, strategy research, execution planning, capital preservation and executive decision intelligence. They remain advisory until separately approved by the relevant control layer.
