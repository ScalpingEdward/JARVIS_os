# PHOENIX v21.226 — Demo 1 Integration Hardening: Router & Runtime Readiness Governance

## Purpose
Move Demo 1 from an isolated vertical-slice module into the live FastAPI application surface and expose a truthful runtime-readiness contract for the remaining integration work.

## Added
- registers the v21.225 Demo 1 router in the application;
- registers the v21.226 runtime-readiness router;
- exposes `GET /phoenix/demo1/v21.226/readiness`;
- reports which Demo 1 integrations are actually bound versus still pending;
- keeps autonomous high-risk execution explicitly disabled;
- provides application-level tests proving the Demo 1 endpoints are mounted and reachable.

## Current readiness boundary
The orchestration route is application-wired, but these production bindings remain pending:
- real STT/TTS adapter;
- persistent approval inbox;
- memory-provider binding;
- operator UI/dashboard;
- concrete tool adapters.

The readiness state therefore remains `degraded`, not `ready`, until those bindings are completed.

## Safety boundary
Router registration does not relax approval governance. High-risk actions remain gated and `autonomous_high_risk_execution_enabled = false`.

## Next
v21.227 — Demo 1 Voice Adapter Contract, STT/TTS Provider Binding & Fallback Governance.
