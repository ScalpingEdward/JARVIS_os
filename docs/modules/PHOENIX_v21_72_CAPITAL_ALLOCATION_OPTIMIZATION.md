# PHOENIX v21.72 — Capital Allocation Optimization Intelligence Governance

## Purpose

PHOENIX v21.72 evaluates proposed portfolio allocations under governed risk, liquidity, concentration and turnover constraints. It produces advisory intelligence only and cannot rebalance portfolios or place orders.

## Intelligence outputs

- Expected portfolio return
- Expected portfolio volatility
- Expected shortfall
- Risk-adjusted efficiency
- Diversification score
- Liquidity score
- Turnover
- Constraint compliance
- Confidence and freshness

## Governed alerts

- Constraint breach
- Concentration alert
- Turnover-limit breach
- Liquidity-floor breach
- Efficiency decay
- Low-confidence escalation

## Lifecycle

`draft -> evidence-ready -> scored -> policy-ready -> review-required -> approved -> active -> monitoring`

Exceptional states include `blocked`, `constraint-breach`, `concentration-alert`, `efficiency-decay`, `escalated`, `suspended`, `revoked` and `archived`.

## API

- `GET /v1/capital-allocation/status`
- `POST /v1/capital-allocation/records`
- `GET /v1/capital-allocation/records`
- `GET /v1/capital-allocation/records/{record_id}`
- `POST /v1/capital-allocation/records/{record_id}/actions`
- `GET /v1/capital-allocation/audit`

## Governance guarantees

- Human approval is mandatory before activation.
- Risk Brain hard blocks are authoritative.
- Operation identifiers provide replay protection.
- Source keys are unique within each workspace.
- Records and audit events are workspace isolated.
- Allocation mutation, fund movement and broker execution are disabled.

## Integration

Governed outputs from PHOENIX v21.62 through v21.71 may contextualize expected regimes, sentiment, institutional flow, derivatives positioning, cross-asset structure, liquidity, execution quality, attribution and portfolio stress. v21.72 converts that context into controlled allocation recommendations without autonomous execution.
