# PHOENIX v21.91 — Agent Objective & Intent Alignment Governance

## Purpose

PHOENIX v21.91 governs whether an AI agent remains aligned with its declared objective, human intent, policy intent, instruction hierarchy, constraints and cross-agent priorities. It is an assurance layer only and cannot rewrite objectives, reprioritize tasks, mutate instructions, execute agent tools or place trades.

## Core controls

- declared-objective alignment
- instruction-hierarchy integrity
- constraint compliance
- priority consistency
- human-intent alignment
- policy-intent alignment
- cross-agent goal consistency
- goal stability
- objective-drift detection
- conflicting-instruction detection
- constraint-breach detection
- priority-inversion detection
- suspected goal-hijack detection
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
- aligned
- objective-drift
- intent-conflict
- constraint-alert
- priority-conflict
- goal-hijack-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-objective-alignment/status`
- `POST /v1/agent-objective-alignment/records`
- `GET /v1/agent-objective-alignment/records`
- `GET /v1/agent-objective-alignment/records/{record_id}`
- `POST /v1/agent-objective-alignment/records/{record_id}/actions`
- `GET /v1/agent-objective-alignment/audit`

## Approval rules

Unresolved objective drift, intent conflicts, constraint breaches, priority conflicts, goal-hijack findings or residual-risk breaches block approval. Activation requires explicit human approval. Critical agents can receive a Risk Brain hard block for suspected goal hijacking, material constraint violations or extreme residual risk.

## Safety boundary

The module explicitly reports:

- `objective_mutation_enabled=false`
- `instruction_mutation_enabled=false`
- `automatic_reprioritization_enabled=false`
- `agent_execution_enabled=false`
- `execution_enabled=false`

It cannot:

- rewrite or replace agent objectives
- mutate instruction hierarchy
- automatically reprioritize tasks
- execute agent tools
- bypass upstream Risk Brain, compliance, model-risk, cybersecurity, memory, runtime or multi-agent governance
- move funds
- mutate portfolios
- submit or execute orders

## Integration

v21.91 extends v21.90 Multi-Agent Coordination & Delegation Governance. Coordinated agents can still be unsafe if their goals drift, their instruction hierarchy is corrupted, priorities invert or human intent is displaced. Objective/intent approval cannot override upstream hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
