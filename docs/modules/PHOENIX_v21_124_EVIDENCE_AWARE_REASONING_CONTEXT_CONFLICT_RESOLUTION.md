# PHOENIX v21.124 — Evidence-Aware Reasoning Context Assembly & Conflict Resolution

## Purpose
v21.124 turns trusted agent memory from v21.123 into bounded, citation-complete reasoning packets for the planner and orchestrator.

## Capabilities
- Trust-threshold filtering across confidence, freshness and source reliability
- Citation-preserving evidence selection
- Claim-key grouping and contradictory-value detection
- Conflict severity classification
- Human conflict-resolution gate
- Aggregate confidence and freshness scoring
- Reasoning-packet integrity digest
- Replay protection, workspace isolation and audit digests
- Risk Brain hard block for critical low-confidence evidence

## Lifecycle
`blocked`, `draft`, `review-required`, `approved`, `ready`, `conflict`, `revoked`, `archived`.

## API
- `GET /v1/evidence-reasoning-context/status`
- `POST /v1/evidence-reasoning-context/records`
- `GET /v1/evidence-reasoning-context/records`
- `GET /v1/evidence-reasoning-context/records/{record_id}`
- `POST /v1/evidence-reasoning-context/records/{record_id}/actions`
- `GET /v1/evidence-reasoning-context/audit`

## Safety boundary
This module assembles reasoning context only. It performs no network fetch, connector invocation, external write, credential or permission mutation, fund movement, order submission or trading execution. Human approval is mandatory before a packet becomes ready for downstream planning.

## Integration
v21.123 admits only approved provenance evidence into bounded memory. v21.124 selects that memory, detects source conflicts and emits a citation-complete reasoning packet for the autonomous planner/orchestrator without granting any new execution authority.
