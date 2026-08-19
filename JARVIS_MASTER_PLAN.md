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
G1-G4 Research, G5-G8 Instagram, G9-G12 Files & Documents and G13-G16 Communications complete.

G17-G20 complete the Trading shadow-only path. G18 implements the local adapter, G19 certifies F1->F2->G18->F3->F4, and G20 adds persistent health evidence, bounded freshness, descriptor fingerprint/config-drift fail-closed certification, Command Centre visibility, persistent operator stop and a `recorded-not-executed` command journal. Broker network, live orders, order modification/cancellation, position mutation and production transport remain disabled.

Phase G continuation:
`G17 Trading shadow selection -> G18 adapter -> G19 E2E -> G20 health/drift + Command Centre -> G21 provider-expansion/promotion decision`.

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
- Phase G G1-G4 Research, G5-G8 Instagram, G9-G12 Files/Documents, G13-G16 Communications: complete.
- G17-G19: Trading shadow selection, adapter and E2E certification complete.
- G20 complete: Trading shadow health evidence is persistent/freshness-bounded; provider/adapter/config drift and unhealthy/missing evidence fail closed; Command Centre exposes descriptor, health, actions, executions, reconciliation, stops and alerts; operator stop persists; commands are recorded-not-executed; broker network/live order/cancel-modify/position mutation/production transport remain disabled.
- Next after G20 merge: G21 — provider-expansion/promotion decision. This must be evidence-driven and must not silently convert shadow certification into live Trading permission.

This checkpoint must be updated at each phase boundary or major activation milestone.