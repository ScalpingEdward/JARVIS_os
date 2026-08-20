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
H1 provides persistent secretless provider contracts. H2 provides the contract-bound Research read-only sandbox adapter. H3 provides persistent E2E/reconciliation certification across H1->H2. H4 adds persistent health/freshness/drift observability. H5 adds a persistent, fail-closed **authorization decision only** for future Research read-only network transport. H5 requires H4 operational readiness, exact contract/adapter/capability binding, credential-reference state consistency, explicit operator approval and rollback/stop readiness. A positive H5 decision still leaves credential resolution, network transport, provider writes and production transport disabled and requires a separate later activation boundary.

Phase H continuation:
`H1 contract registry -> H2 read-only sandbox adapter -> H3 E2E/reconciliation -> H4 health/drift/observability -> H5 network-transport authorization decision -> H6 read-only network transport boundary`.

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
- H1-H4 complete: secretless Research external read-only sandbox path is contract-bound, reconciled, health/freshness/drift observable and fail-closed; no credential resolution/network/write/production transport enabled.
- H5 complete: network-transport authorization is now a persistent evidence-driven decision artifact. Authorization requires valid H1-H4 state, exact read-only capability scope, credential-reference presence, explicit operator approval and stop/rollback readiness. The decision itself cannot resolve credentials or enable network/provider-write/production transport.
- Next after H5 merge: H6 — Research read-only network transport boundary. It must consume a positive H5 decision, resolve credentials only through an isolated reference resolver, enforce GET/read-only semantics and hard budgets, retain kill-switch/rollback controls, and remain disabled by default until separately activated.

This checkpoint must be updated at each phase boundary or major activation milestone.