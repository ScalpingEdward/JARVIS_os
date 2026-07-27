# PHOENIX v21.115 — Multi-Agent Orchestrator Runtime

## Purpose
v21.115 is the first controlled runtime coordination layer above the v21.114 Autonomous Task Planner and v21.113 Agent Capability Registry. It binds planned tasks to eligible agents and governs task status, handoff and validation state without yet allowing agents or tools to execute external side effects.

## Core functions
- Bind planned tasks to eligible registered agents
- Match capability, tool and data-domain requirements
- Enforce confidence thresholds
- Track dependency-aware task readiness
- Track running, waiting, handoff and validation states
- Require validation before completion
- Track attempts and assignment readiness
- Preserve workspace isolation and replay protection
- Produce complete orchestration audit records
- Escalate critical unresolved orchestration risk to Risk Brain

## Lifecycle
`draft`, `ready`, `review-required`, `approved`, `dispatch-ready`, `running`, `waiting`, `handoff-required`, `validation-required`, `completed`, `blocked`, `suspended`, `cancelled`, `archived`.

## API
- `GET /v1/multi-agent-orchestrator/status`
- `POST /v1/multi-agent-orchestrator/records`
- `GET /v1/multi-agent-orchestrator/records`
- `GET /v1/multi-agent-orchestrator/records/{record_id}`
- `POST /v1/multi-agent-orchestrator/records/{record_id}/actions`
- `GET /v1/multi-agent-orchestrator/audit`

## Safety boundary
This release enables assignment and orchestration-state management only. It does **not** dispatch real agents, invoke tools, mutate credentials or permissions, change infrastructure, shift traffic, alter portfolios or routing, move funds, submit orders or execute trades.

Human approval is mandatory before dispatch preparation. `dispatch-ready` is an authorization boundary, not actual dispatch. Real tool/agent execution belongs to a separately permissioned sandbox/runtime layer.

## Integration
- v21.113: defines eligible agents and their capabilities/tools/domains.
- v21.114: generates the approved task graph.
- v21.115: binds tasks to agents and governs status/handoffs/validation.
- v21.116 should add the controlled Tool Execution Sandbox and execution envelopes required for real, permission-scoped actions.
