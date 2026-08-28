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
H1-H39 establish and certify the governed Research provider path through bounded activation, one persistent revocable transport identity, one inert read-only injected transport object, one short-lived revocable one-shot network-execution authorization, one certified fail-closed exactly-once consumption boundary and one certified consumed authorization with exactly one bounded read-only request reserved. H40 adds the design-only request execution contract for that single certified reservation: immutable request identity, exact read-only transport-call signature, bounded timeout/response/error semantics and append-only audit/reconciliation requirements. H40 sends no provider traffic and does not resolve credentials.

Phase H continuation:
`H1 contract registry -> H2 read-only sandbox adapter -> H3 E2E/reconciliation -> H4 health/drift/observability -> H5 network authorization decision -> H6 read-only network boundary -> H7 boundary E2E certification -> H8 real-provider readiness decision -> H9 provider adapter contract design -> H10 contract certification -> H11 provider adapter skeleton -> H12 skeleton E2E certification -> H13 real-provider activation boundary design -> H14 activation boundary certification -> H15 one-shot canary activation gate -> H16 canary execution boundary design -> H17 canary execution boundary certification -> H18 one-shot canary execution gate -> H19 transport injection contract -> H20 transport injection contract certification -> H21 transport injection activation design -> H22 transport injection activation design certification -> H23 transport injection authorization gate -> H24 transport injection boundary design -> H25 transport injection boundary certification -> H26 transport binding gate -> H27 transport binding certification -> H28 transport object injection design -> H29 transport object injection design certification -> H30 transport object injection gate -> H31 transport object injection certification -> H32 network execution authorization design -> H33 network execution authorization design certification -> H34 network execution authorization gate -> H35 network execution authorization certification -> H36 network execution boundary design -> H37 network execution boundary certification -> H38 network execution gate -> H39 network execution gate certification -> H40 request execution design -> H41 request execution design certification`.

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
- H21-H31 complete: governed transport activation, authorization, binding, injection design/certification and exactly one inert read-only transport object are established and certified with network execution disabled.
- H32-H35 complete: one short-lived operator-bound revocable one-shot network-execution authorization is designed, certified, issued and certified again against exact transport/object/identity scope while provider traffic remains disabled.
- H36-H37 complete: the fail-closed exactly-once consumption boundary is designed and certified with expiry/revocation/read-only scope and zero network state.
- H38 complete: one clean unexpired H37-certified authorization is consumed exactly once and exactly one bounded read-only request is reserved; provider traffic remains disabled.
- H39 complete: certification verifies exact H38/H37/H36/H35/H34/H33/H32/H31/H30 lineage, exactly-once consumption, exactly one reserved request, expiry/revocation/read-only scope and zero provider traffic/credential/write/production state.
- H40 complete: design-only request execution contract binds one clean H39-certified reservation to one immutable request identity and exact GET transport-call signature, bounded timeout/response/error behavior, metadata/hash-only audit and exactly-once reconciliation semantics. The request remains unexecuted and network/credential/write/production execution remains disabled.
- Next after H40 merge: H41 — Research real-provider request execution design certification. Certify exact H40/H39/H38 lineage, immutable request identity, transport-call signature, response/timeout/error bounds, audit/reconciliation semantics and continued zero-execution/zero-provider-traffic state before any request execution gate.

This checkpoint must be updated at each phase boundary or major activation milestone.
