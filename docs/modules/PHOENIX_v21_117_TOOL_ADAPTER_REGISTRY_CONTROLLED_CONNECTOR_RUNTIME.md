# PHOENIX v21.117 — Tool Adapter Registry & Controlled Connector Runtime

## Purpose
v21.117 adds the controlled discovery and eligibility layer for external tool connectors. v21.116 defines the sandbox authorization boundary; v21.117 defines which concrete adapter is allowed to satisfy a sandboxed tool request.

## Core capabilities
- Adapter identity, version and connector type registry
- Supported tool and operation declarations
- Permission-scope and data-domain matching
- Side-effect posture and mandatory human-approval metadata
- Health and reliability thresholds
- Rate-limit and timeout metadata
- Allowed-host and denied-operation declarations
- Credential references without exposing credential material
- Active-adapter matching for future controlled connector invocation
- Replay protection, workspace isolation and audit trail
- Risk Brain hard blocks for fund movement, order submission, trading execution, credential mutation and safety-control disabling

## Endpoints
- `GET /v1/tool-adapters/status`
- `POST /v1/tool-adapters/records`
- `GET /v1/tool-adapters/records`
- `GET /v1/tool-adapters/records/{record_id}`
- `POST /v1/tool-adapters/records/{record_id}/actions`
- `POST /v1/tool-adapters/match`
- `GET /v1/tool-adapters/audit`

## Safety boundary
Registry and adapter matching are enabled. Real connector invocation remains disabled in v21.117. The module does not expose credential material, move funds, submit orders, execute trades, mutate safety controls, change permissions or mutate infrastructure.

Human approval is required before adapter activation. Adapters with unresolved findings cannot be approved. Protected financial or safety-control operations trigger a Risk Brain hard block.

## Integration
v21.115 binds tasks to agents. v21.116 authorizes tool intent inside the sandbox. v21.117 resolves that authorized intent to an eligible external adapter. A later release can add a controlled invocation gateway while preserving the sandbox, registry, approval and Risk Brain boundaries.
