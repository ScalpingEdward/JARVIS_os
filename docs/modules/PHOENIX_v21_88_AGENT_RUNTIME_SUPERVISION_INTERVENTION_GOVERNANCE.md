# PHOENIX v21.88 — Agent Runtime Supervision & Intervention Governance

## Purpose

PHOENIX v21.88 governs the runtime behavior of already-authorized AI agents. It evaluates runtime health, behavioral drift, repeated-action loops, tool reliability, budget/resource pressure, context integrity and human-intervention readiness. The module is advisory and governance-only: it does not execute tools, stop agents, mutate permissions, alter infrastructure or submit trades.

## Core controls

- heartbeat health
- behavioral stability
- policy conformance
- tool success and output-validation rates
- human-override readiness
- stop-control readiness
- resource efficiency and budget headroom
- context integrity
- repeated-action / runaway-loop detection
- consecutive tool-failure detection
- policy-violation detection
- resource-spike detection
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
- healthy
- behavior-drift
- loop-alert
- tool-failure-alert
- budget-alert
- intervention-required
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-runtime-supervision/status`
- `POST /v1/agent-runtime-supervision/records`
- `GET /v1/agent-runtime-supervision/records`
- `GET /v1/agent-runtime-supervision/records/{record_id}`
- `POST /v1/agent-runtime-supervision/records/{record_id}/actions`
- `GET /v1/agent-runtime-supervision/audit`

## Approval rules

Records with unresolved behavior, tool-failure, loop, budget, intervention or residual-risk findings cannot be approved. Activation requires prior human approval. Critical agents with failed human override, policy violations, extreme runaway-loop behavior or high residual risk receive a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `agent_execution_enabled=false`
- `automatic_agent_stop_enabled=false`
- `automatic_intervention_enabled=false`
- `tool_execution_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

It cannot:

- execute agent tools
- automatically stop or restart agents
- grant or revoke permissions
- mutate credentials
- change infrastructure
- move funds
- mutate portfolios or routing
- submit or execute orders

## Integration

v21.88 sits above v21.87 Agent Authorization & Tool-Use Governance. v21.87 answers whether an agent is authorized to request a capability; v21.88 answers whether the authorized agent remains healthy and controllable while operating. Runtime supervision cannot override Risk Brain, compliance, cybersecurity, data-governance, model-risk, operational-resilience, release, asset-integrity or authorization hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are rejected per workspace and operation receipts are replay-protected.
