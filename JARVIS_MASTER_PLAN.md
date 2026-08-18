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
F1 defines bounded authorization. F2 provides the adapter-separated hard-budget execution boundary. F3 requires immediate result reconciliation and forced stop on mismatch/failure/safety drift. F4 certifies the completed canary and emits only a promotion, rollback or hold authorization decision. Promotion remains separate from unrestricted production transport and cannot enable it directly.

Phase F sequence complete:
`F1 controlled provider canary authorization contract -> F2 controlled canary execution boundary -> F3 immediate result reconciliation/stop enforcement -> F4 canary certification and promotion/rollback decision`.

### Phase G — Provider-specific controlled canary integration
G1 begins only after F4 merge. A real provider/vertical may be selected only through a dedicated adapter integration preserving the F1-F4 controls. No generic or cross-provider transport activation is allowed.

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
- Phase F F1-F4: complete architecture after F4 merge.
- F4 complete: canary evidence is revalidated against actual submitted executions and F3 reconciliation state; every submitted action must reconcile; any stop or failed stop forces rollback; health/policy/safety controls are rechecked; explicit operator approval is required for promotion; and the promotion artifact always keeps `unrestricted_production_enabled_by_decision=False`.
- Next after F4 merge: G1 — provider-specific canary adapter selection and integration, preserving all existing budgets, stop/reconciliation gates and disabled-by-default production transport.

This checkpoint must be updated at each phase boundary or major activation milestone.