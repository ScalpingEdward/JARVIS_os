# PHOENIX v21.114 — Autonomous Task Planner

## Purpose
v21.114 is the first planner-facing layer in the PHOENIX runtime path. It converts a human-approved goal into a structured task graph with dependencies, capability requirements, tool requirements, data-domain requirements, budgets, timeouts and approval gates.

## Planning model
- Goal and success criteria
- Task decomposition
- Dependency graph
- Capability requirements
- Tool requirements
- Data-domain requirements
- Budget allocation
- Parallelism limits
- Timeout limits
- Human-approval markers
- Readiness state

## Safety boundary
Planning is enabled, execution is not. This module does not dispatch agents, call tools, mutate credentials or permissions, change infrastructure, mutate portfolios or routing, move funds, submit orders or execute trades.

Any task carrying execution permission is flagged. Critical plans with execution permission or excessive residual risk can trigger a Risk Brain hard block. Human approval is required before a plan can become `ready`.

## Integration
v21.113 answers which agents are eligible for capabilities and tools. v21.114 defines the task graph that a future orchestrator can consume. v21.115 should provide the controlled multi-agent orchestration runtime that binds approved tasks to eligible registered agents without bypassing PHOENIX safety gates.

## API
- `GET /v1/autonomous-task-planner/status`
- `POST /v1/autonomous-task-planner/records`
- `GET /v1/autonomous-task-planner/records`
- `GET /v1/autonomous-task-planner/records/{record_id}`
- `POST /v1/autonomous-task-planner/records/{record_id}/actions`
- `GET /v1/autonomous-task-planner/audit`
