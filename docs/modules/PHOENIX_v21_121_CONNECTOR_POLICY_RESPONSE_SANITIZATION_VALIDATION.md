# PHOENIX v21.121 — Connector Policy Profiles & Response Sanitization / Schema Validation

## Purpose
v21.121 hardens the read-only external execution path introduced in v21.120. It allows multiple read-only connectors to share a common execution boundary while applying connector-specific response policies before any external data is accepted by PHOENIX.

## Core controls
- Connector-specific policy profiles
- Allowed content types
- Maximum response size
- Required schema fields
- Allowed top-level fields
- Unknown-field rejection/removal
- Secret and credential redaction
- Denied sensitive fields
- HTML stripping
- String-length limits
- Collection-size limits
- Response validation state and immutable-style receipt digest
- Human approval before policy activation
- Replay protection and workspace isolation
- Risk Brain hard block for unsafe critical profiles

## Governed response lifecycle
`received`, `sanitized`, `validated`, `accepted`, `rejected`, `blocked`.

## API
- `GET /v1/connector-response-policy/status`
- `POST /v1/connector-response-policy/policies`
- `GET /v1/connector-response-policy/policies`
- `GET /v1/connector-response-policy/policies/{record_id}`
- `POST /v1/connector-response-policy/policies/{record_id}/actions`
- `POST /v1/connector-response-policy/responses`
- `GET /v1/connector-response-policy/responses`
- `GET /v1/connector-response-policy/responses/{response_id}`
- `POST /v1/connector-response-policy/responses/{response_id}/accept`
- `GET /v1/connector-response-policy/audit`

## Safety boundary
This module sanitizes and validates read-only connector responses only. It does not perform external network calls, write operations, credential mutation, permission escalation, fund movement, order submission or trading execution.

Raw external responses are not forwarded directly into downstream agent context. A response must pass the active connector profile, sanitization and schema validation before it can reach the accepted state.

## Integration
v21.120 governs read-only external request execution. v21.121 governs the trust boundary on the return path: external response → connector policy → sanitization → schema validation → explicit acceptance.

## Next
v21.122 should add trusted external data provenance and freshness governance, binding accepted responses to source identity, timestamps, evidence hashes and confidence/freshness metadata for downstream agent reasoning.
