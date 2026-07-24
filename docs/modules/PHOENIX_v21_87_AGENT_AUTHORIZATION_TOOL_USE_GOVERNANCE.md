# PHOENIX v21.87 — Agent Authorization & Tool-Use Governance

## Purpose

PHOENIX v21.87 governs AI-agent authority, tool access, delegation, data access and high-impact autonomy. The module is an assurance and authorization layer only. It does not grant credentials, mutate tool permissions, execute agent actions, place orders or alter portfolio state.

## Core controls

- least-privilege scoring
- requested-versus-approved scope analysis
- tool allowlist coverage
- explicit authorization coverage
- human-approval coverage
- delegation-chain controls
- prompt-injection resilience
- sensitive-data access controls
- output validation
- auditability and reversibility
- unauthorized tool-attempt detection
- unapproved delegation detection
- prompt-injection event detection
- autonomous high-impact action detection
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
- authorized
- scope-alert
- tool-alert
- delegation-alert
- injection-alert
- data-access-alert
- autonomy-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-authorization/status`
- `POST /v1/agent-authorization/records`
- `GET /v1/agent-authorization/records`
- `GET /v1/agent-authorization/records/{record_id}`
- `POST /v1/agent-authorization/records/{record_id}/actions`
- `GET /v1/agent-authorization/audit`

## Approval rules

Records with unresolved authorization, scope, delegation, injection, data-access, autonomy or residual-risk findings cannot be approved. Activation requires a prior human approval state. Critical agents with unauthorized tool use, autonomous high-impact actions or extreme residual risk receive a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `agent_execution_enabled=false`
- `tool_permission_mutation_enabled=false`
- `credential_mutation_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

It cannot:

- execute agent tool calls
- grant or revoke tool permissions
- create, expose or rotate credentials
- bypass upstream compliance, cybersecurity, data-governance or model-risk controls
- move funds
- mutate portfolios
- submit or execute orders

## Integration

v21.87 sits above v21.86 Configuration & Asset Integrity Governance. v21.86 verifies the integrity of the production asset and configuration estate; v21.87 governs what AI agents are allowed to request or recommend on top of that trusted estate. Agent authorization cannot override Risk Brain, compliance, cybersecurity, model-risk, data-governance, operational-resilience, release-governance or configuration-integrity hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
