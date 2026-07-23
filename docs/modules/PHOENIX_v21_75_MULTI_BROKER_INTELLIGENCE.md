# PHOENIX v21.75 — Autonomous Multi-Broker Intelligence Governance

## Purpose

PHOENIX v21.75 evaluates broker and venue quality across execution, latency, liquidity, reliability, regulatory standing, counterparty resilience and capacity. It produces governed routing recommendations only.

## Core capabilities

- Broker and venue quality scoring
- Spread, slippage, latency, fill-rate and rejection analysis
- Uptime and partial-fill monitoring
- Liquidity and capacity assessment
- Counterparty and regulatory resilience scoring
- Concentration-aware routing recommendations
- Advisory routing-weight normalization and broker caps
- Latency, execution-degradation, counterparty and capacity alerts
- Human approval workflow
- Operation-receipt replay protection
- Workspace isolation and duplicate source-key protection
- Complete audit trail
- Risk Brain hard-block authority

## States

`blocked`, `draft`, `evidence-ready`, `scored`, `policy-ready`, `review-required`, `approved`, `active`, `monitoring`, `stable`, `latency-alert`, `execution-degradation`, `counterparty-alert`, `capacity-alert`, `routing-review`, `escalated`, `suspended`, `revoked`, `archived`

## API

- `GET /v1/multi-broker-intelligence/status`
- `POST /v1/multi-broker-intelligence/records`
- `GET /v1/multi-broker-intelligence/records`
- `GET /v1/multi-broker-intelligence/records/{record_id}`
- `POST /v1/multi-broker-intelligence/records/{record_id}/actions`
- `GET /v1/multi-broker-intelligence/audit`

## Safety boundary

This module is intelligence and governance only. It cannot:

- submit or cancel orders;
- alter broker credentials or configuration;
- mutate live routing tables;
- move funds;
- rebalance capital;
- execute through a broker or venue.

Human approval is mandatory before governance activation. Risk Brain hard blocks remain authoritative. Status explicitly reports:

- `broker_configuration_mutation_enabled=false`
- `routing_mutation_enabled=false`
- `fund_movement_enabled=false`
- `execution_enabled=false`

## Integration

v21.75 consumes governed context produced by the macro, sentiment, flow, derivatives, cross-asset, liquidity, transaction-cost, attribution, portfolio-risk, allocation, scenario and adaptive-strategy layers. It converts broker telemetry into auditable advisory routing intelligence without crossing the execution boundary.
