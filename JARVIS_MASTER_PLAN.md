# JARVIS / AURON — Canonical Master Plan

Status: canonical project roadmap
Repository: `ScalpingEdward/JARVIS_os`

## 1. Mission

JARVIS is the master operating system. AURON is its controlled intelligence/orchestration layer. The product is not a single Telegram bot, trading bot, or social-media tool. Those are vertical capabilities operated through one governed core, one Command Centre, shared identity/audit state, and explicit safety boundaries.

The build must preserve sequence. Do not skip a required foundation layer merely because a downstream feature can already be prototyped.

## 2. Source-of-truth rule for every new chat/build session

Before building the next PR:

1. Read this file from `main`.
2. Verify the last claimed PR is actually merged into `main`.
3. Inspect the current module/route on `main` rather than relying only on chat memory.
4. Continue from `Current checkpoint` below and the dependency graph.
5. Never restart an already merged layer and never invent a PR/merge state.
6. If implementation reality and this roadmap disagree, reconcile them explicitly before advancing.

## 3. Architecture invariants

- JARVIS = master OS and unified operator experience.
- AURON = orchestration/intelligence/governance layer.
- Command Centre = operational interface; it must remain distinct from public/landing-page UI.
- Every consequential external action must have an explicit execution boundary, observable result, audit trail and failure state.
- Dry-run/simulation must remain possible independently of live execution.
- Provider adapters must not bypass central policy/risk/approval controls.
- Idempotency, reconciliation, health state and fail-closed behavior are core infrastructure, not optional feature polish.
- Secrets/tokens never belong in source control.
- External execution is enabled only when its dedicated integration and safety gates are complete.

## 4. Completed foundation lineage

The long Telegram successor-generation series established controlled activation, succession, monitoring, drift governance, immutable evidence, baseline certification, continuity, expiry and renewal patterns. Generation Forty-Six closes that repeated successor loop at v21.523.

v21.523 is therefore a phase boundary, not permission to discard the established architecture. The next phase converts the foundation into integration-ready reusable product infrastructure.

## 5. Mandatory build sequence from v21.523

### Phase A — Integration readiness and core cutover
A1. Canonical roadmap + integration-readiness registry.
A2. Unified capability/adapter contract.
A3. Persistent execution/audit ledger and idempotency/reconciliation primitives.
A4. Central policy gate.
A5. Command Centre integration.
A6. End-to-end integration harness and cutover certification.

### Phase B — Trading vertical
Trading architecture completed through B10. Live-provider execution remains deliberate and gated.

### Phase C — Instagram Content Manager vertical
Content architecture completed through C8. Provider writes remain deliberate and gated.

### Phase D — Additional verticals

Communications D1-D8: completed.
Research D9-D16: completed.
Automation D17-D24: completed.

The fourth Phase D vertical is **Files & Documents**: governed file/folder discovery, metadata, version identity, content inspection and later controlled document/file mutations. This vertical gives JARVIS a durable knowledge/document workspace without allowing storage-provider writes to bypass approval, version checks or reconciliation.

Files & Documents sequence:
`D25 provider/adapter onboarding contract -> D26 file/folder/version registry + normalized state -> D27 read/list/search/fetch integration -> D28 provenance/version/access policy -> D29 deterministic mutation simulation/dry-run -> D30 controlled create/update/move boundary -> D31 reconciliation/conflict/retry/delete safeguards -> D32 Files & Documents Command Centre operations`.

D25 is strictly read-only certification. A provider may advertise write/delete support, but those capabilities remain disabled until their dedicated later gates.

Automation workflows may coordinate Trading, Content, Communications, Research or Files & Documents only through each vertical's governed public boundaries. They may never call provider transports behind policy/risk/version layers.

No new vertical may bypass the shared AURON core simply because its provider API is easy to call.

## 6. Cross-vertical Command Centre requirements

The operational interface must ultimately provide persistent command/text interaction, system/capability health, simulation/live visibility, pending approvals, execution timeline/failures, dedicated Trading/Content/Communications/Research/Automation/Files workspaces, global and capability kill switches, and audit/evidence access.

A landing page or decorative footer must never replace the operational command field.

## 7. Definition of usable

A vertical is not considered usable merely because routes exist. Minimum usable state requires provider health, persistent state, policy before outbound action, idempotency/reconciliation, operator-visible results, kill/disable controls, failure/replay tests, and deliberate live enablement.

## 8. PR discipline

Each PR should implement one coherent layer, include tests, document dependencies and state the next layer. Before merge, verify CI and mergeability. After the user reports merge, verify GitHub before creating the next branch.

Do not generate endless successor generations after v21.523 unless a concrete architectural requirement demands it. Continue the planned phase sequence instead.

## 9. Current checkpoint

- Foundation successor loop completed through v21.523.
- Phase A core cutover completed through A6.
- Phase B Trading architecture completed through B10; live-provider execution remains disabled by default until real transport and live gates are satisfied.
- Phase C Instagram Content Manager completed through C8; provider writes remain disabled by default.
- Phase D Communications completed through D8.
- Phase D Research completed through D16.
- Phase D Automation completed through D24; execution transports and cross-vertical execution remain disabled by default, and recorded commands cannot bypass governance.
- Current phase: Phase D — Files & Documents vertical.
- Completed: D25 — Files & Documents selected as the fourth Phase D vertical; onboarding contract requires stable provider identity, authenticated/reachable read access, explicit read-only scope, metadata/content inspection and stable version identity. Write/delete remain explicitly disabled even when advertised by a provider.
- Next after D25 merge: D26 — persistent provider-neutral file/folder/version registry and normalized state, still without storage mutations.

This section must be updated when phase boundaries or major activation milestones change so a new chat can recover the correct trajectory from the repository itself.
