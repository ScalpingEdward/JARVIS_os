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
Communications D1-D8: completed.
Research D9-D16: completed.
Automation D17-D24: completed.
Files & Documents D25-D32: completed architecture.

### Phase E — Cross-vertical integration certification
E1-E4 completed: common governance certification, deterministic cross-vertical simulation, reconciliation/observability certification and production-readiness/canary eligibility. E4 never enables provider transport.

### Phase F — Controlled provider canary program
F1-F4 completed: bounded authorization, adapter-separated hard-budget execution, immediate result reconciliation/forced stop, and promotion/rollback/hold certification. Promotion never directly enables unrestricted production transport.

### Phase G — Provider-specific controlled canary integration
G1-G4 complete the Research read-only canary path. G5-G8 complete the Instagram local draft-preview canary path.

G9 selects Files & Documents as the third provider-specific canary. G10 implements `documents-readonly-canary-v1` / `documents-local-readonly` with persistent local metadata/version-preview evidence and compatibility with F2 execution plus F3 result/stop boundaries. The adapter explicitly rejects content-bearing and mutation payloads; provider mutation, delete, move, network transport and production transport remain disabled.

Phase G continuation:
`G9 Files/Documents selection -> G10 Documents readonly canary adapter -> G11 Documents E2E certification -> G12 Documents health/drift + Command Centre certification -> G13 next provider/vertical selection`.

## 6. Cross-vertical Command Centre requirements
Persistent command/text interaction, capability health, simulation/execution visibility, approvals, execution timeline/failures, dedicated vertical workspaces, kill switches and audit/evidence access remain mandatory.

## 7. Definition of usable
A vertical requires observable provider health, persistent state, policy before outbound action, idempotency/reconciliation, visible results, disable controls, failure/replay tests and deliberate external enablement.

## 8. PR discipline
One coherent layer per PR, with tests, dependencies and next layer documented. Verify merge before advancing.

## 9. Current checkpoint
- Foundation through v21.523: complete.
- Phase A through A6: complete.
- Trading B1-B10: complete architecture; provider execution gated.
- Instagram Content C1-C8: complete architecture; writes gated.
- Communications D1-D8: complete.
- Research D9-D16: complete.
- Automation D17-D24: complete; external execution disabled by default.
- Files & Documents D25-D32: complete architecture; provider mutation disabled by default and delete denied.
- Phase E E1-E4: complete.
- Phase F F1-F4: complete.
- Phase G G1-G4: Research provider-specific canary path complete.
- Phase G G5-G8: Instagram provider-specific canary path complete with publish/write/network/production disabled.
- G9 complete: Files & Documents selected as the next safe local provider-specific canary.
- G10 complete: Documents local read-only adapter persists metadata/version-preview actions, is F2/F3 compatible, guarantees zero external calls, refuses content/mutation fields, and keeps mutation/delete/move/network/production disabled.
- Next after G10 merge: G11 — full Documents F1->F2->G10->F3->F4 end-to-end certification with idempotency, provider/action binding, reconciliation and fail-closed mutation-safety assertions.

This checkpoint must be updated at each phase boundary or major activation milestone.