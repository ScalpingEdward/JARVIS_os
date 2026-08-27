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
H1-H25 establish and certify the governed Research provider path through a bounded session, zero-transport injection contract, activation design/certification, short-lived authorization and transport-injection boundary. H26 consumes exactly one clean H25-certified H23 authorization to bind one persistent revocable transport identity. The binding inherits exact operator/provider/capability/HTTPS endpoint/GET/request-budget/timeout/response-size/opaque transport-ref scope and starts with zero requests used. No concrete transport object is injected and network, credential-resolution, provider-write and production execution remain disabled.

Phase H continuation:
`H1 contract registry -> H2 read-only sandbox adapter -> H3 E2E/reconciliation -> H4 health/drift/observability -> H5 network authorization decision -> H6 read-only network boundary -> H7 boundary E2E certification -> H8 real-provider readiness decision -> H9 provider adapter contract design -> H10 contract certification -> H11 provider adapter skeleton -> H12 skeleton E2E certification -> H13 real-provider activation boundary design -> H14 activation boundary certification -> H15 one-shot canary activation gate -> H16 canary execution boundary design -> H17 canary execution boundary certification -> H18 one-shot canary execution gate -> H19 transport injection contract -> H20 transport injection contract certification -> H21 transport injection activation design -> H22 transport injection activation design certification -> H23 transport injection authorization gate -> H24 transport injection boundary design -> H25 transport injection boundary certification -> H26 transport binding gate -> H27 transport binding certification`.

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
- H1-H20 complete: Research provider path is contract-bound, reconciled, certified through one bounded transport-disabled session and zero-concrete-transport injection contract.
- H21 complete: design-only transport injection activation pins H20/H19/H18 identity, opaque transport reference and mandatory read-only/reapproval/kill/rollback controls without authorization or injection.
- H22 complete: certification verifies exact H21/H20/H19/H18 binding, HTTPS GET/provider/capability/budget identity, opaque transport reference, all mandatory controls and zero authorization/transport/network/credential/write state.
- H23 complete: a clean H22 certification can issue exactly one short-lived operator-bound transport-injection authorization after fresh re-approval and kill/rollback readiness. Authorization remains `authorized-not-injected-not-executable`; no transport, network, credential resolution or provider writes are enabled.
- H24 complete: design-only transport-injection boundary defines exactly-once H23 authorization consumption into one transport identity binding, revocable lifecycle semantics, inherited request budget and metadata/hash-only audit safety. Authorization remains unconsumed and no transport is bound, injected or network-executable.
- H25 complete: certification verifies exact H24/H23 authorization binding, exactly-once consumption semantics, transport identity/lifecycle/revocation, budget/timeout/response-size and audit invariants, plus continued zero-injection/zero-network/zero-credential/write state.
- H26 complete: one clean H25-certified H23 authorization is consumed exactly once into one persistent revocable transport identity binding with exact certified scope and zero requests used. Concrete transport injection and all network/credential/write execution remain disabled.
- Next after H26 merge: H27 — Research real-provider transport binding certification. Certify exact H25/H24/H23 binding consumption, persistent transport identity uniqueness/revocation, inherited scope/budget and continued zero concrete transport/network state before any transport-object injection layer.

This checkpoint must be updated at each phase boundary or major activation milestone.