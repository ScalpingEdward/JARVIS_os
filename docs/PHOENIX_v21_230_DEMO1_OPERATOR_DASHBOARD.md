# PHOENIX v21.230 — Demo 1 Operator UI Dashboard Contract & Unified System Surface Governance

## Purpose
Provide one operator-facing contract that composes Demo 1 readiness, voice, approvals, memory and tool-adapter state into a single governed system surface.

## Added
- unified dashboard snapshot for one workspace/operator;
- system-readiness, approval-inbox, memory-context, voice-interface and tool-adapter panels;
- explicit attention routing for degraded or actionable panels;
- stable navigation map to the underlying canonical APIs;
- approval counts from the persistent v21.228 inbox;
- memory status from the canonical v21.229 binding;
- voice provider visibility from the existing voice subsystem;
- Risk Brain hard block propagates across the complete dashboard surface;
- autonomous high-risk execution remains disabled.

## API
`POST /phoenix/demo1/v21.230/dashboard`

The dashboard is a backend UI contract that a web/desktop operator shell can render without duplicating system-state logic in the client.

## Boundary
This module does not bypass the canonical voice, approval, memory, tool or execution services. It aggregates their state and navigation surfaces only.

## Readiness progression
After v21.230, `operator-ui-dashboard` is considered bound. The remaining Demo 1 integration debt is `concrete-tool-adapters`.

## Next
v21.231 — Demo 1 Concrete Tool Adapter Registry, Capability Health & Governed Invocation Contract.
