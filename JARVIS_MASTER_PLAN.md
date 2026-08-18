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
Files & Documents D25-D32: completed architecture.

### Phase E — Cross-vertical integration certification
E1 certifies the common governance contract across Trading, Instagram Content, Communications, Research, Automation and Files & Documents. Every vertical must prove persistent state, policy, simulation, execution boundary, reconciliation, kill/disable controls and Command Centre/command-field presence. Recorded commands cannot directly execute and live transports cannot default on.

Phase E sequence begins:
`E1 cross-vertical integration certification -> E2 end-to-end cross-vertical simulation harness -> E3 shared audit/replay certification -> E4 production-readiness/canary gate`.

No Phase E step silently enables provider transports.

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
- Files & Documents D25-D32: complete architecture; provider mutation disabled by default and delete denied.
- Current phase: Phase E — cross-vertical integration certification.
- E1 complete: evidence-driven fail-closed certification requires all six verticals, validates common governance primitives, forbids direct command execution, forbids default-live transports and forbids cross-vertical provider bypass. E1 itself enables no live transport.
- Next after E1 merge: E2 — deterministic end-to-end cross-vertical simulation harness proving governed handoffs between vertical boundaries without provider writes/live execution.

This checkpoint must be updated at each phase boundary or major activation milestone.