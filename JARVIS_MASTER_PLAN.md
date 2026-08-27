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
H1-H31 establish and certify the governed Research provider path through bounded activation, authorization, one persistent revocable transport identity and one inert read-only injected transport object. H32 defines the explicit short-lived, operator-bound, exactly-once network-execution authorization artifact tied to one clean H31-certified injection, with fresh reapproval, kill-switch and rollback preconditions. H32 is design-only: no authorization is issued or consumed and network, credential-resolution, provider-write and production execution remain disabled.

Phase H continuation:
`H1 contract registry -> H2 read-only sandbox adapter -> H3 E2E/reconciliation -> H4 health/drift/observability -> H5 network authorization decision -> H6 read-only network boundary -> H7 boundary E2E certification -> H8 real-provider readiness decision -> H9 provider adapter contract design -> H10 contract certification -> H11 provider adapter skeleton -> H12 skeleton E2E certification -> H13 real-provider activation boundary design -> H14 activation boundary certification -> H15 one-shot canary activation gate -> H16 canary execution boundary design -> H17 canary execution boundary certification -> H18 one-shot canary execution gate -> H19 transport injection contract -> H20 transport injection contract certification -> H21 transport injection activation design -> H22 transport injection activation design certification -> H23 transport injection authorization gate -> H24 transport injection boundary design -> H25 transport injection boundary certification -> H26 transport binding gate -> H27 transport binding certification -> H28 transport object injection design -> H29 transport object injection design certification -> H30 transport object injection gate -> H31 transport object injection certification -> H32 network execution authorization design -> H33 network execution authorization design certification`.

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
- H21 complete: design-only transport injection pins H20/H19/H18 identity, opaque transport reference and mandatory controls without authorization or injection.
- H22 complete: certification verifies exact H21/H20/H19/H18 binding and zero authorization/transport/network/credential/write state.
- H23 complete: one short-lived operator-bound transport-injection authorization can be issued after fresh reapproval; no transport/network execution is enabled.
- H24 complete: design-only transport-injection boundary defines exactly-once H23 authorization consumption into one transport identity binding.
- H25 complete: certification verifies H24/H23 binding, exactly-once consumption semantics, lifecycle/revocation, budget and audit invariants.
- H26 complete: one clean H25-certified H23 authorization is consumed exactly once into one persistent revocable transport identity binding.
- H27 complete: certification verifies H26 binding lineage, exact inherited scope and zero-network state.
- H28 complete: design-only transport-object injection contract binds exactly to one clean H27-certified identity.
- H29 complete: certification verifies exact H28/H27/H26 identity lineage, object contract/scope, lifecycle/revocation and zero-network state.
- H30 complete: one inert read-only transport object is attached exactly once to one clean H29-certified identity with zero requests used.
- H31 complete: certification verifies exact injected-object lineage, uniqueness, deterministic fingerprint, revocation semantics and continued zero network/credential/write/production execution.
- H32 complete: design-only short-lived operator-bound one-shot network-execution authorization is defined against one clean H31-certified injected object, with exact scope, 30–300 second TTL, fresh reapproval, kill-switch/rollback readiness and metadata/hash-only audit semantics. Authorization remains unissued/unconsumed and network execution remains disabled.
- Next after H32 merge: H33 — Research real-provider network execution authorization design certification. Certify exact H32/H31/H30 identity/scope binding, TTL/one-shot/reapproval/kill/rollback/audit invariants and continued zero-issued/zero-network state before any authorization gate.

This checkpoint must be updated at each phase boundary or major activation milestone.
