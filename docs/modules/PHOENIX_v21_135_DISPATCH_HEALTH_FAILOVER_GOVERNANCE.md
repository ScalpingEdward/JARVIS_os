# PHOENIX v21.135 — Dispatch Health Evaluation & Governed Failover Trigger Verification

## Purpose
Evaluate runtime health evidence against the approved v21.134 primary/standby dispatch plan and its deterministic failover criteria.

## Health evidence
- primary availability
- latency threshold
- receipt reconciliation quality
- worker heartbeat
- gateway health
- adapter health
- confidence and freshness

## Governed trigger set
- `primary-unavailable`
- `latency-degraded`
- `receipt-reconciliation-degraded`
- `worker-heartbeat-lost`
- `gateway-unhealthy`
- `adapter-unhealthy`

## Lifecycle
`blocked`, `evidence-ready`, `healthy`, `degraded`, `review-required`, `approved`, `failover-authorized`, `revoked`, `archived`.

## Safety boundary
This module evaluates evidence and can issue a non-executing failover authorization only after human approval. It does not mutate routes, dispatch traffic, invoke external connectors, expand permissions, move funds, submit orders or execute trades. Risk Brain remains authoritative.

## Integration
v21.134 defines primary/standby dispatch planning. v21.135 verifies when the approved failover criteria are actually satisfied. v21.136 can bind an approved authorization to a short-lived, single-use standby failover permit.
