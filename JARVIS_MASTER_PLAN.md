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
H1-H19 establish the governed Research provider path through a one-shot bounded session and a design-only injectable transport contract. H20 certifies the H19 contract against the exact H18 session, including provider/capability/HTTPS endpoint binding, GET-only interface semantics, fail-closed 1..10 request-budget/sequential-request invariants, bounded timeout/response-size limits and continued absence of concrete transport. H20 remains certification-only and performs no transport injection, networking, credential resolution or provider writes.

Phase H continuation:
`H1 contract registry -> H2 read-only sandbox adapter -> H3 E2E/reconciliation -> H4 health/drift/observability -> H5 network authorization decision -> H6 read-only network boundary -> H7 boundary E2E certification -> H8 real-provider readiness decision -> H9 provider adapter contract design -> H10 contract certification -> H11 provider adapter skeleton -> H12 skeleton E2E certification -> H13 real-provider activation boundary design -> H14 activation boundary certification -> H15 one-shot canary activation gate -> H16 canary execution boundary design -> H17 canary execution boundary certification -> H18 one-shot canary execution gate -> H19 transport injection contract -> H20 transport injection contract certification -> H21 transport injection activation design`.

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
- H1-H12 complete: Research provider path is contract-bound, reconciled, health/drift observable, structurally certified and skeleton-E2E-certified with zero real provider calls.
- H13-H14 complete: design-only activation boundary and its certification pin identity/scope, expiry/budget, one-shot/kill/rollback/re-approval controls and zero-transport state.
- H15 complete: a clean H14 certification can produce exactly one short-lived, operator-bound, revocable `armed-not-executable` canary token. Token issuance requires fresh operator re-approval plus kill/rollback readiness; all network/credential-resolution/write/production flags remain disabled.
- H16 complete: the separate execution-boundary design binds exactly one H15 token to one operator/provider/capability/endpoint, defines exactly-once token consumption into one bounded session, fail-closed request-budget enforcement and hash/metadata-only audit semantics. No token consumption or concrete provider transport exists yet.
- H17 complete: certification verifies exact H15 token/boundary identity, exactly-once consumption semantics, HTTPS endpoint/capability/request-budget enforcement, audit safety and zero-transport state. Certification itself performs no token consumption, credential resolution, provider networking or writes.
- H18 complete: the execution gate can consume one clean H17-certified H15 token exactly once and persist one bounded transport-disabled session. Provider/network/credential/write/production execution remains disabled.
- H19 complete: the transport injection interface and persistent session-bound contract define exact endpoint/capability, GET-only sequential requests, fail-closed request-budget enforcement, bounded timeout/response size and zero concrete transport state.
- H20 complete: certification verifies the exact H19 contract/H18 session binding, interface semantics, endpoint/capability/budget/sequence enforcement, timeout/response-size bounds and zero concrete transport/network/credential/write state.
- Next after H20 merge: H21 — Research real-provider transport injection activation design. Define how one clean H20 certification could authorize a separately injected read-only transport instance while keeping actual network execution behind a later explicit gate.

This checkpoint must be updated at each phase boundary or major activation milestone.