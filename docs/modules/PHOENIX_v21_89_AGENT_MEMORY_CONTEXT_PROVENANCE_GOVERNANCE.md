# PHOENIX v21.89 — Agent Memory & Context Provenance Governance

## Purpose

PHOENIX v21.89 governs AI-agent memory trust, context provenance, freshness, contamination resistance, retention and sensitive-memory controls. It is an assurance layer only and does not write, delete, inject or alter agent memory.

## Core controls

- source-authority scoring
- provenance coverage
- context freshness and stale-read detection
- relevance and conflict-resolution assurance
- memory contamination resilience
- conflicting-memory detection
- retention-policy compliance
- sensitive-memory access controls
- deletion traceability
- confidence-weighted aggregate assurance
- critical-agent Risk Brain hard blocks

## Lifecycle

- blocked
- draft
- evidence-ready
- assessed
- review-required
- approved
- active
- monitoring
- trusted
- provenance-alert
- stale-context-alert
- contamination-alert
- retention-alert
- sensitive-memory-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-memory-context/status`
- `POST /v1/agent-memory-context/records`
- `GET /v1/agent-memory-context/records`
- `GET /v1/agent-memory-context/records/{record_id}`
- `POST /v1/agent-memory-context/records/{record_id}/actions`
- `GET /v1/agent-memory-context/audit`

## Approval rules

Unresolved provenance, freshness, contamination, retention, sensitive-memory or residual-risk findings block approval. Activation requires prior human approval. Critical agents with contaminated memory, sensitive-memory incidents or extreme residual risk receive a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `memory_mutation_enabled=false`
- `context_injection_enabled=false`
- `automatic_memory_deletion_enabled=false`
- `agent_execution_enabled=false`
- `execution_enabled=false`

It cannot mutate memory, inject context, delete retained information, alter permissions, move funds, mutate portfolios, submit orders or execute trades.

## Integration

v21.89 extends v21.88 from runtime behavior into memory and context trust. A healthy runtime can still make unsafe decisions when its memory is stale, contaminated, unverifiable or improperly retained. Memory/context approval cannot override Agent Authorization, Runtime Supervision, Risk Brain, compliance, cybersecurity, model-risk or data-governance hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
