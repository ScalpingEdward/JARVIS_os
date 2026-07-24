# PHOENIX v21.90 — Multi-Agent Coordination & Delegation Governance

## Purpose

PHOENIX v21.90 governs cooperation between multiple AI agents after authorization, runtime supervision and memory/context assurance. It evaluates role clarity, delegation integrity, handoffs, consensus, conflict resolution, shared context and human escalation readiness without executing agent actions or mutating authority.

## Core controls

- role and responsibility clarity
- task ownership integrity
- delegation-chain integrity
- unauthorized delegation detection
- handoff quality and failed-handoff detection
- consensus alignment
- unresolved disagreement detection
- coordination deadlock detection
- shared-context consistency
- human escalation readiness
- confidence and freshness weighting
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
- coordinated
- role-conflict
- delegation-alert
- consensus-alert
- deadlock-alert
- handoff-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/multi-agent-coordination/status`
- `POST /v1/multi-agent-coordination/records`
- `GET /v1/multi-agent-coordination/records`
- `GET /v1/multi-agent-coordination/records/{record_id}`
- `POST /v1/multi-agent-coordination/records/{record_id}/actions`
- `GET /v1/multi-agent-coordination/audit`

## Approval rules

Unresolved role, delegation, consensus, deadlock, handoff or residual-risk findings block approval. Activation requires prior human approval. Critical agents with unauthorized delegation, repeated deadlocks or extreme residual risk trigger a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `agent_execution_enabled=false`
- `delegation_mutation_enabled=false`
- `task_assignment_mutation_enabled=false`
- `automatic_consensus_execution_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

It cannot execute tools, assign tasks, mutate delegation authority, automatically resolve consensus, move funds, alter portfolios, change routing or submit orders.

## Integration

v21.90 extends v21.89 from trusted memory/context into governed cooperation between agents. Valid memory does not guarantee safe collaboration: authority boundaries, handoffs, consensus and escalation paths remain independently governed. Multi-agent approval cannot override Agent Authorization, Runtime Supervision, Memory/Context Provenance, Risk Brain, compliance, cybersecurity, model-risk or data-governance hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
