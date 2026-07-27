# PHOENIX v21.113 — Agent Capability Registry

## Purpose
v21.113 introduces the capability registry required for the upcoming autonomous planner and multi-agent orchestrator. PHOENIX can now maintain an explicit, reviewable description of what each agent is allowed to do, which tools it may use, which data domains it may access, and which operational limits apply.

## Registry model
Each agent profile declares:
- agent identity and version
- operational role
- capabilities
- tool grants and tool-level permissions
- read-only vs mutable tool posture
- human-approval requirements
- per-task tool-call limits
- allowed data domains
- explicitly denied actions
- parallel-task limit
- task timeout
- daily budget units
- confidence floor
- criticality
- accountable human owner

## Capability matching
`POST /v1/agent-capabilities/match` accepts required capabilities, tools, data domains and a minimum confidence threshold. Only ACTIVE profiles can be returned as eligible. Matching is advisory and does not assign or execute tasks.

## Lifecycle
`draft -> review-required -> approved -> active`

Operational states also support `degraded`, `suspended`, `revoked` and `archived`.

## Safety controls
- mutable tool grants without human approval are flagged
- excessive tool-call or parallel-task limits are flagged
- critical low-confidence agents can trigger Risk Brain hard block
- unresolved registry findings block approval
- activation requires prior human approval
- replay protection, workspace isolation and duplicate source-key protection are enforced

## Safety boundary
The registry does not execute tasks or tools, create credentials, mutate permissions, change infrastructure, alter portfolios or routing, move funds, submit orders or execute trades.

## Integration
v21.112 defines a safe execution contract. v21.113 defines which agent is eligible to receive a future task or contract. v21.114 can therefore build the Autonomous Task Planner on top of a controlled capability-discovery layer instead of hard-coded agent selection.
