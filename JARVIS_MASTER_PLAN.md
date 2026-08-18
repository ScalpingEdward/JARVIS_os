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
E1 certifies the common governance contract across Trading, Instagram Content, Communications, Research, Automation and Files & Documents.

E2 adds deterministic end-to-end cross-vertical simulation through named governed boundaries, with stable replay identity and zero provider writes.

E3 adds persistent reconciliation and observability certification, including correlation identity, lineage, failure visibility and side-effect/drift detection.

E4 adds the production-readiness/canary gate. A candidate provider/vertical must carry E1-E3 proof, green health and policy state, idempotency/reconciliation, explicit operator approval, a tightly bounded canary scope, rollback/stop control and an available kill switch that remains active during certification. Provider transport must be configured but disabled while E4 evaluates readiness. E4 does not switch any provider transport on.

Phase E sequence complete:
`E1 governance certification -> E2 cross-vertical simulation -> E3 reconciliation/observability certification -> E4 production-readiness/canary gate`.

### Phase F — Controlled provider canary program
Phase F begins only after E4 merge. F1 defines a separate canary-control contract for one explicitly selected provider/vertical. Passing E4 indicates readiness for that later controlled decision; it does not change provider execution state.

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
- Phase E E1-E4: complete architecture after E4 merge.
- E4 complete: evidence-driven readiness gate requires prior certification, provider health/policy, idempotency, reconciliation, operator approval, bounded scope, active safety controls and rollback/stop capability; E4 itself changes no provider execution state.
- Next after E4 merge: F1 — controlled provider canary contract, remaining disabled by default.

This checkpoint must be updated at each phase boundary or major activation milestone.