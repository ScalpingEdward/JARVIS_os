# PHOENIX v21.129 — Controlled Read-Only Dispatch Eligibility & One-Time Execution Permit Governance

## Purpose
v21.129 sits after v21.128 End-to-End Execution Authorization Chain Verification. It converts only a fully eligible authorization chain into a short-lived, single-use, read-only execution permit.

The module does not perform the external dispatch itself. It governs whether a downstream worker may receive a one-time permit.

## Required bindings
Each permit is bound to:

- workspace
- v21.128 authorization-chain record and digest
- operation and target
- GET/HEAD method
- adapter identity
- worker identity
- gateway record
- dispatch-token digest

A mismatch during permit consumption fails closed.

## Permit lifecycle

`review-required -> approved -> issued -> consumed`

Terminal alternatives:

- `blocked`
- `expired`
- `revoked`
- `archived`

A permit is single-use and cannot be consumed again after its first successful consumption.

## Safety controls

- maximum one use
- maximum policy TTL of 300 seconds
- conservative short-lived issuance window
- human approval before issuance
- Risk Brain authoritative
- upstream hard-block propagation
- protected-operation hard blocks
- replay protection
- workspace isolation
- duplicate source-key protection
- immutable-style audit event digests

## Protected operations
The permit layer hard-blocks fund movement, order submission, trading execution, credential mutation, permission escalation, safety-control disabling and destructive repository operations.

## Safety boundary

- read-only permit governance only
- GET/HEAD only
- no direct external dispatch in this module
- no connector bypass
- no credential or permission mutation
- no fund movement
- no order submission
- no trading execution

## Integration

`Decision -> Proposal -> Safe-Execution Binding -> End-to-End Authorization Verification -> One-Time Permit -> downstream controlled read-only dispatch`

## Next
v21.130 should add One-Time Permit Dispatch Handoff & Execution Receipt Reconciliation, consuming a v21.129 permit exactly once and reconciling the downstream worker/executor receipt back to the permit, gateway and authorization-chain digests without enabling write or trading execution.
