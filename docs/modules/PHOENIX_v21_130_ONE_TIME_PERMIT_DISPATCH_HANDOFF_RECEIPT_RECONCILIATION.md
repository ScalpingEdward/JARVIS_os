# PHOENIX v21.130 — One-Time Permit Dispatch Handoff & Execution Receipt Reconciliation

## Purpose
v21.130 closes the controlled read-only dispatch loop. It consumes an approved v21.129 single-use permit, binds the handoff to the exact authorization chain, gateway, worker, adapter, operation and target, and then reconciles the downstream execution receipt back to those identities and digests.

## Core controls
- GET/HEAD-only handoff contract
- Human approval before handoff
- Single-use permit consumption
- Permit expiry enforcement
- Authorization-chain digest binding
- Gateway dispatch-token digest binding
- Worker and adapter identity binding
- Operation and target binding
- Response and receipt digest capture
- Fail-closed receipt mismatch detection
- Deterministic handoff and reconciliation digests
- Replay protection, workspace isolation and duplicate source-key protection
- Risk Brain hard blocks for protected operations or write methods

## Lifecycle
`review-required` → `approved` → `handoff-ready` → `permit-consumed` → `dispatched` → `reconciled`

Exceptional states: `blocked`, `failed`, `mismatch`, `revoked`, `archived`.

## Safety boundary
This module coordinates governance state and receipt reconciliation only. It does not embed a direct external network client. Fund movement, order submission, trading execution, credential mutation, permission escalation and safety-control disabling remain prohibited.

## Integration
v21.128 verifies the complete authorization chain. v21.129 issues the short-lived single-use read-only permit. v21.130 consumes that permit exactly once, records the controlled dispatch handoff, and verifies that the returned execution receipt belongs to the same authorized chain.

## Next
v21.131 should add Post-Execution Outcome Validation & Side-Effect Attestation, comparing the reconciled receipt to expected postconditions and verifying that the supposedly read-only operation produced no prohibited side effects.
