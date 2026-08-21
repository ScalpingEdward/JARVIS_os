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
Research G1-G4, Instagram G5-G8, Files & Documents G9-G12, Communications G13-G16 and Trading-shadow G17-G20 are complete. G21 completes the evidence-driven expansion decision.

### Phase H — Controlled external-provider sandbox integration
H1-H9 establish the Research read-only external-provider path through real-provider contract design without enabling real provider traffic. H10 certifies the H9 provider contract against clean H8 readiness evidence and structural safety invariants: exact provider/environment binding, exact endpoint allowlist, GET-only approved capabilities, secretref-only read-only credential semantics, minimum audit evidence, no raw credential/response persistence, and preservation of the design-only boundary. H10 still implements no provider client, credential resolver or network transport.

Phase H continuation:
`H1 contract registry -> H2 read-only sandbox adapter -> H3 E2E/reconciliation -> H4 health/drift/observability -> H5 network authorization decision -> H6 read-only network boundary -> H7 boundary E2E certification -> H8 real-provider readiness decision -> H9 provider adapter contract design -> H10 provider adapter contract certification -> H11 provider adapter implementation skeleton`.

## 6. Cross-vertical Command Centre requirements
Persistent command/text interaction, capability health, simulation/execution visibility, approvals, execution timeline/failures, dedicated vertical workspaces, kill switches and audit/evidence access remain mandatory.

## 7. Definition of usable
A vertical requires observable provider health, persistent state, policy before outbound action, idempotency/reconciliation, visible results, disable controls, failure/replay tests and deliberate external enablement.

## 8. PR discipline
One coherent layer per PR, with tests, dependencies and next layer documented. Verify merge before advancing.

## 9. Current checkpoint
- Foundation through v21.523 and Phase A A1-A6: complete.
- Trading B1-B10, Instagram C1-C8 and Phase D vertical architecture: complete with consequential provider execution gated.
- Phase E E1-E4, Phase F F1-F4 and Phase G through G21: complete.
- H1-H7 complete: Research external read-only sandbox/network boundary is contract-bound, reconciled, health/drift observable and E2E-certified with deterministic fakes; no provider writes and no real provider transport enabled.
- H8 complete: real-provider activation readiness is a persistent decision artifact requiring non-production provider identity, HTTPS allowlist, safe credential provenance, read-only scope, operator approval and stop/rollback readiness; no real traffic is activated.
- H9 complete: persistent provider-specific adapter contract design defines GET-only HTTPS capability bindings, response normalization labels, secretref-only read-only resolver semantics and safe audit persistence.
- H10 complete: H8 readiness and H9 contract design are structurally certified together; provider/environment and endpoint allowlist must match, only approved GET capabilities are accepted, credential/audit contracts remain safe, and any provider client/network/write/production capability blocks certification. Real network, credential resolution, writes and production transport remain disabled.
- Next after H10 merge: H11 — Research real-provider adapter implementation skeleton. Implement the provider-specific adapter shape and normalization/audit plumbing against injected resolver/transport interfaces only; keep concrete provider networking absent and runtime transport disabled by default.

This checkpoint must be updated at each phase boundary or major activation milestone.