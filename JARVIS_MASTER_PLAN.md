# JARVIS / AURON — Canonical Master Plan

Status: canonical project roadmap
Repository: `ScalpingEdward/JARVIS_os`

## 1. Mission
JARVIS is the master operating system. AURON is its controlled intelligence/orchestration layer. Vertical capabilities operate through one governed core, one Command Centre, shared identity/audit state, and explicit safety boundaries. Build sequence must be preserved.

## 2. Source-of-truth rule for every new chat/build session
1. Read this file from `main`.
2. Verify the last claimed PR is actually merged into `main`.
3. Inspect current implementation on `main`.
4. Continue from the checkpoint and dependency graph.
5. Never restart merged layers or invent merge state.
6. Reconcile implementation and roadmap explicitly if they disagree.

## 3. Architecture invariants
- JARVIS = master OS; AURON = orchestration/intelligence/governance.
- Command Centre remains operational UI with persistent command/text interaction.
- Consequential external actions require explicit execution boundaries, observable results, audit and failure state.
- Simulation remains independent of external execution.
- Provider adapters cannot bypass central policy/risk/approval controls.
- Idempotency, reconciliation, health, provenance/version state and fail-closed behavior are core infrastructure.
- Secrets never belong in source control.
- External execution is deliberate, never default.

## 4. Completed foundation lineage
Foundation successor governance closed at v21.523. Phase A core cutover is complete through A6.

## 5. Mandatory build sequence
### Phase B — Trading
Completed through B10; provider execution remains gated.
### Phase C — Instagram Content Manager
Completed through C8; provider writes remain gated.
### Phase D — Additional verticals
Communications D1-D8, Research D9-D16, Automation D17-D24 and Files & Documents D25-D32 completed.
### Phase E — Cross-vertical integration certification
E1-E4 completed.
### Phase F — Controlled provider canary program
F1-F4 completed.
### Phase G — Provider-specific controlled canary integration
Research G1-G4, Instagram G5-G8, Files & Documents G9-G12, Communications G13-G16 and Trading-shadow G17-G20 are complete. G21 completes the evidence-driven expansion decision and selects Research for external read-only sandbox design only.

### Phase H — Controlled external-provider sandbox integration
H1 implements a persistent external-provider contract registry and secretless sandbox boundary. Contracts declare vertical/provider/adapter/environment/capabilities and may contain only an opaque credential reference; raw secret material is rejected. H1 allows only read-only sandbox contracts and cannot enable provider writes, network transport or production transport.

Planned Phase H sequence:
`H1 provider contract registry + secretless sandbox boundary -> H2 research external-readonly sandbox adapter -> H3 external sandbox E2E/reconciliation -> H4 health/drift/observability -> H5 explicit network-transport authorization decision`.

## 6. Cross-vertical Command Centre requirements
Persistent command/text interaction, capability health, simulation/execution visibility, approvals, execution timeline/failures, dedicated vertical workspaces, kill switches and audit/evidence access remain mandatory.

## 7. Definition of usable
A vertical requires observable provider health, persistent state, policy before outbound action, idempotency/reconciliation, visible results, disable controls, failure/replay tests and deliberate external enablement.

## 8. PR discipline
One coherent layer per PR, with tests, dependencies and next layer documented. Verify merge before advancing.

## 9. Current checkpoint
- Foundation through v21.523 and Phase A A1-A6: complete.
- Trading B1-B10: architecture complete; provider execution gated.
- Instagram C1-C8: architecture complete; writes gated.
- Communications D1-D8, Research D9-D16, Automation D17-D24, Files & Documents D25-D32: complete.
- Phase E E1-E4 and Phase F F1-F4: complete.
- Phase G provider-specific canary paths and G21 expansion decision: complete.
- H1 complete: persistent external-provider contracts, bounded capability declarations and opaque credential references are supported; raw secrets are rejected; only read-only sandbox contracts are accepted; public descriptors never expose credential references; network/write/production transport remain unauthorized.
- Next after H1 merge: H2 — Research external read-only sandbox adapter. It must consume an H1 contract and remain transport-disabled by default; credential resolution and real network calls remain separate authorization gates.

This checkpoint must be updated at each phase boundary or major activation milestone.