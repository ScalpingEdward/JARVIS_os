# PHOENIX v21.122 — External Data Provenance, Freshness & Evidence Governance

## Purpose
v21.122 governs the trust boundary after v21.121 has sanitized and schema-validated an external response. It binds accepted data to source identity, timestamps, evidence hashes, payload digests, freshness, confidence and source reliability before downstream agents may rely on it.

## Core assurance
- Connector and source identity binding
- Source URI and source timestamp capture
- Observation timestamp capture
- Evidence hash and payload digest binding
- Freshness scoring
- Confidence and source-reliability scoring
- Corroboration metadata
- Accepted-response verification
- Sanitization/schema-validation inheritance
- Evidence bundle digest and immutable-style audit digests

## Governed signals
`active`, `stale`, `low-confidence`, `evidence-gap`.

## API
- `GET /v1/external-data-provenance/status`
- `POST /v1/external-data-provenance/records`
- `GET /v1/external-data-provenance/records`
- `GET /v1/external-data-provenance/records/{record_id}`
- `POST /v1/external-data-provenance/records/{record_id}/actions`
- `GET /v1/external-data-provenance/audit`

## Safety boundary
This module does not fetch external data, mutate external systems, forward raw unsanitized responses, change credentials or permissions, move funds, submit orders or execute trades. It only establishes provenance and evidence assurance for data already accepted by upstream response policy controls.

Human approval is required before evidence becomes active. Stale, low-confidence, invalid or unaccepted critical evidence can trigger Risk Brain hard block.

## Integration
v21.120 governs outbound read-only execution. v21.121 sanitizes and validates responses. v21.122 determines whether the accepted result is sufficiently attributable, fresh, intact and trustworthy for downstream agent reasoning.
