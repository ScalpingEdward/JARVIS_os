# PHOENIX v21.140 — One-Time Recovery Permit & Primary Handoff Governance

## Purpose

v21.140 converts a human-approved, ready v21.139 recovery-to-primary plan into a short-lived, single-use recovery permit bound to the exact primary adapter, worker, gateway and policy chain.

## Governance boundary

This module does not execute network calls, mutate routing, move funds, submit orders or perform trading execution. Permit consumption is only a governed handoff signal for downstream controlled execution layers.

## Core controls

- Admission only from `ready` recovery plans
- Recovery plan, recovery-readiness and dispatch-plan digest binding
- Exact primary adapter, primary worker and gateway identity binding
- Sandbox, gateway and worker policy-digest binding
- Human review and approval before issuance
- Single-use opaque permit token with digest storage
- Short-lived issuance window
- Fail-closed token, plan and identity verification at consume time
- Protected-operation Risk Brain hard blocks
- Replay protection
- Workspace isolation
- Duplicate source-key protection
- Immutable-style audit evidence

## Lifecycle

`blocked → plan-ready → review-required → approved → issued → consumed`

Administrative/terminal states: `expired`, `revoked`, `archived`.

## Endpoints

- `GET /v1/recovery-primary-permits/status`
- `POST /v1/recovery-primary-permits/records`
- `GET /v1/recovery-primary-permits/records`
- `GET /v1/recovery-primary-permits/records/{permit_id}`
- `POST /v1/recovery-primary-permits/records/{permit_id}/actions`
- `POST /v1/recovery-primary-permits/records/{permit_id}/consume`
- `GET /v1/recovery-primary-permits/audit`

## Integration

v21.138 establishes recovery readiness. v21.139 creates the bounded recovery-to-primary plan. v21.140 binds that approved plan to the exact primary handoff chain and produces a one-time permit without bypassing sandbox, gateway, worker, receipt or Risk Brain controls.

## Next

v21.141 should add Governed Primary Recovery Reconciliation & Recovery Completion Attestation, reconciling a consumed v21.140 permit against downstream primary-path receipts and proving the recovery completed inside the approved read-only safety boundary.
