# PHOENIX v21.123 — Trusted Context Ingestion & Evidence-Aware Agent Memory

## Purpose
v21.123 is the controlled bridge from approved external evidence into bounded agent context. It accepts only provenance-backed evidence, preserves citations and evidence digests, enforces freshness/confidence thresholds and prevents expired or low-trust context from reaching downstream reasoning.

## Capabilities
- Approved provenance admission
- Evidence bundle and provenance-record binding
- Source URI and citation preservation
- Confidence, source-reliability and freshness thresholds
- TTL-based context expiry
- Project/session/workspace memory scopes
- Topic and data-domain filters
- Bounded confidence/freshness-aware retrieval ranking
- Explicit exclusion of revoked, expired, stale or unapproved records
- Replay protection, workspace isolation and duplicate source-key protection
- Risk Brain hard block for critical invalid evidence
- Immutable-style audit event digests

## API
- `GET /v1/trusted-agent-memory/status`
- `POST /v1/trusted-agent-memory/records`
- `GET /v1/trusted-agent-memory/records`
- `GET /v1/trusted-agent-memory/records/{record_id}`
- `POST /v1/trusted-agent-memory/records/{record_id}/actions`
- `POST /v1/trusted-agent-memory/retrieve`
- `GET /v1/trusted-agent-memory/audit`

## Safety boundary
This module performs context admission and retrieval only. It does not fetch external data, accept raw unsanitized responses, mutate credentials or permissions, perform external writes, move funds, submit orders or execute trades. Human approval is required before a memory record becomes active.

## Integration
v21.121 sanitizes and validates external responses. v21.122 establishes source provenance, evidence integrity, freshness and confidence. v21.123 allows only that approved evidence into bounded agent memory while preserving source attribution for downstream reasoning.

## Next
v21.124 should assemble evidence-aware reasoning packets, detect contradictions across trusted sources and require citation-complete context before the autonomous planner/orchestrator can consume external evidence.
