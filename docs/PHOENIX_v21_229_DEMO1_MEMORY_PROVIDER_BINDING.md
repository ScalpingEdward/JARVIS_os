# PHOENIX v21.229 — Demo 1 Memory Provider Binding & Context Retrieval Governance

## Purpose
Bind the existing persistent PHOENIX memory service to the Demo 1 orchestration surface so operator requests can retrieve relevant context from the canonical memory provider instead of relying on a boolean `memory_context_available` flag.

## Added
- Demo 1 memory provider contract backed by the existing `memory_service` / `SQLMemoryStore`;
- provider status endpoint;
- governed context retrieval endpoint;
- category and minimum-priority filtering;
- bounded result limit;
- deterministic relevance scoring using query match, tags/category and memory priority;
- optional content redaction while preserving metadata;
- Risk Brain hard block prevents context release;
- live FastAPI router registration;
- runtime readiness now reports `memory_provider_bound = true`.

## API
- `GET /phoenix/demo1/v21.229/memory/status`
- `POST /phoenix/demo1/v21.229/memory/context`

## Existing memory surface reused
PHOENIX already exposes persistent memory create/list/search/delete paths. v21.229 reuses that canonical store instead of introducing a second memory database.

## Safety boundary
This binding performs contextual retrieval only. It does not autonomously create, modify or delete operator memories and it does not weaken any execution or approval gate.

`autonomous_memory_mutation_enabled = false`
`autonomous_high_risk_execution_enabled = false`

## Readiness
Completed integration debt:
- voice adapter binding;
- persistent approval inbox;
- memory-provider binding.

Remaining Demo 1 integration priorities:
1. operator UI/dashboard;
2. concrete tool adapters.

## Next
v21.230 — Demo 1 Operator UI Dashboard Contract & Unified System Surface Governance.
