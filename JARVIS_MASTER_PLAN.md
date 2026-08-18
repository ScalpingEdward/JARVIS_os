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
- Simulation remains independent of live execution.
- Provider adapters cannot bypass central policy/risk/approval controls.
- Idempotency, reconciliation, health, provenance/version state and fail-closed behavior are core infrastructure.
- Secrets never belong in source control.
- External execution is deliberate, never default.

## 4. Completed foundation lineage
Foundation successor governance closed at v21.523. Phase A core cutover is complete through A6.

## 5. Mandatory build sequence
### Phase B — Trading
Completed through B10; live provider transport remains gated.

### Phase C — Instagram Content Manager
Completed through C8; provider writes remain gated.

### Phase D — Additional verticals
Communications D1-D8: completed.
Research D9-D16: completed.
Automation D17-D24: completed.

Files & Documents sequence:
`D25 provider/adapter onboarding contract -> D26 file/folder/version registry + normalized state -> D27 read/list/search/fetch integration -> D28 provenance/version/access policy -> D29 deterministic mutation simulation/dry-run -> D30 controlled create/update/move boundary -> D31 reconciliation/conflict/retry/delete safeguards -> D32 Files & Documents Command Centre operations`.

D25-D28 do not mutate provider storage. D28 establishes the fail-closed authorization boundary for future mutation simulation: registered provenance, explicit actor/provider/item access grants and exact current file-version identity are required. Mutation execution remains unauthorized.

Automation may coordinate verticals only through governed public boundaries and never behind policy/risk/version layers.

## 6. Cross-vertical Command Centre requirements
Persistent command/text interaction, capability health, simulation/live visibility, approvals, execution timeline/failures, dedicated vertical workspaces, kill switches and audit/evidence access remain mandatory.

## 7. Definition of usable
A vertical requires observable provider health, persistent state, policy before outbound action, idempotency/reconciliation, visible results, disable controls, failure/replay tests and deliberate live enablement.

## 8. PR discipline
One coherent layer per PR, with tests, dependencies and next layer documented. Verify merge before advancing.

## 9. Current checkpoint
- Foundation through v21.523: complete.
- Phase A through A6: complete.
- Trading B1-B10: complete architecture; live transport gated.
- Instagram Content C1-C8: complete architecture; writes gated.
- Communications D1-D8: complete.
- Research D9-D16: complete.
- Automation D17-D24: complete; execution/cross-vertical transports disabled by default.
- Current phase: Phase D — Files & Documents.
- D25 complete: provider onboarding contract with read-only certification and stable version identity.
- D26 complete: persistent provider-neutral file/folder/version registry, stable identities, parent relationships and immutable version binding.
- D27 complete: onboarding-certified provider list/search/fetch integration populates D26 and verifies exact provider item/version/content identity while preserving zero storage mutations.
- D28 complete: explicit provider/item access grants with revocation, registered-provenance checks and exact current-version authorization for future mutation simulation. Provider-wide grants are supported only when explicitly created. Mutation execution remains fail-closed and cannot be granted in D28.
- Next after D28 merge: D29 — deterministic mutation simulation/dry-run for create/update/move intents, bound to D28 authorization and exact version/provenance state, with zero provider writes.

This checkpoint must be updated at each phase boundary or major activation milestone.