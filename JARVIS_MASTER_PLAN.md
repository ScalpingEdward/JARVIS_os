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
E1-E4 completed.

### Phase F — Controlled provider canary program
F1-F4 completed.

### Phase G — Provider-specific controlled canary integration
G1-G4 Research complete. G5-G8 Instagram complete. G9-G12 Files & Documents complete.

G13 selects **Communications** as the fourth provider-specific canary under the same conservative sequencing policy. The selected provider/adapter is `communications-local-draft` / `communications-draft-canary-v1`, restricted to `render-message-preview` and `inspect-recipient-plan`. Outbound message sending, provider writes, network transport and production transport remain disabled. Trading shadow remains deferred until Communications completes; live order placement remains ineligible.

Phase G continuation:
`G13 Communications selection -> G14 Communications draft canary adapter -> G15 Communications E2E certification -> G16 Communications health/drift + Command Centre certification -> G17 next provider/vertical selection`.

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
- Phase G G1-G4: Research provider-specific canary complete.
- Phase G G5-G8: Instagram provider-specific canary complete.
- Phase G G9-G12: Files & Documents provider-specific canary complete.
- G13 complete: deterministic selection excludes the three completed provider canaries, selects Communications as the lowest-risk remaining side-effect-free local candidate, restricts it to message-preview/recipient-plan inspection, keeps outbound sends disabled, defers trading shadow, and keeps live Trading ineligible.
- Next after G13 merge: G14 — implement `communications-draft-canary-v1` with persistent local preview/recipient-plan state, F2 execution compatibility, F3 result/stop compatibility and zero outbound/network transport.

This checkpoint must be updated at each phase boundary or major activation milestone.