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
A2. Unified capability/adapter contract: simulation vs live, health, permissions, readiness, external-call accounting.
A3. Persistent execution/audit ledger and idempotency/reconciliation primitives.
A4. Central policy gate: operator approval, environment mode, kill switch, capability scopes.
A5. Command Centre integration: real backend state, actions, errors, approvals and audit timeline; preserve text/command interaction field.
A6. End-to-end integration harness and cutover certification.

Do not activate a real external provider before A1–A6 gates applicable to that provider are green.

### Phase B — Trading vertical

Goal: professional multi-account trading operations, including prop-firm accounts and broker accounts, controlled centrally through JARVIS/AURON.

Required capabilities:

- Account registry for multiple prop firms/brokers/accounts with account type, phase/funded state and provider-specific constraints.
- Per-account rule profiles: daily drawdown, max drawdown, profit target, minimum trading days, news restrictions, holding-time restrictions, EA/grid/hedging/copy constraints, consistency or payout-cycle constraints when applicable.
- Normalize balances, equity, floating P/L, realized P/L, exposure, open orders/positions and trading-day state.
- Strategy/signal intake separated from execution.
- Pre-trade risk engine calculates account-specific permitted risk and rejects non-compliant orders before provider execution.
- Multi-account allocation/copy engine must transform a master intent into account-safe child intents; no blind lot copying.
- Explicit protection against prohibited cross-account hedging or other prop-rule violations.
- Daily-DD/max-DD guard, exposure caps, loss limits, symbol/session/news gates and emergency global/per-account kill switches.
- MT5/broker adapter layer with deterministic order IDs, retries, reconciliation and partial-fill/error handling.
- Paper/simulation mode first; then controlled live canary; then multi-account live activation.
- Command Centre: accounts, rule headroom, positions, risk, execution status, alerts, kill switches and audit history.

Trading activation order:
`read-only account sync -> paper intents -> risk-gated simulated execution -> single-account controlled live -> reconciliation proof -> multi-account controlled live`.

Initial Trading build order:
`B1 multi-account registry + provider/rule profiles -> B2 normalized account state -> B3 strategy/signal intake -> B4 pre-trade risk engine -> B5 allocation/copy engine -> B6 account/session/news guards + kill switches -> B7 MT5/broker adapter read-only/paper -> B8 reconciliation/canary certification -> B9 controlled multi-account live -> B10 Command Centre trading operations`.

No strategy is allowed to bypass account rules merely because it is profitable in backtests.

### Phase C — Instagram Content Manager vertical

Goal: manage content production and publishing through the same governed JARVIS/AURON core.

Required capabilities:

- Brand/account registry and content calendar.
- Idea -> draft -> assets -> review -> approval -> scheduled -> publishing -> result lifecycle.
- Caption/hashtag/creative metadata and version history.
- Meta/Instagram provider adapter with token/permission health.
- Draft and preview remain separate from publish permission.
- Explicit approval gate before outbound publishing unless a future automation policy has been deliberately authorized.
- Scheduler, retries, idempotent publish IDs, reconciliation and failure reporting.
- Command Centre queue/calendar/status/analytics/audit views.

Activation order:
`local drafts -> provider read/health -> scheduled dry-run -> controlled publish -> reconciliation -> recurring automation`.

Initial Content build order:
`C1 brand/account registry + content calendar -> C2 lifecycle + version history -> C3 Meta/Instagram read & health adapter -> C4 draft/preview/approval policy -> C5 scheduler + dry-run -> C6 controlled Meta publish boundary -> C7 publish reconciliation/retries -> C8 Content Command Centre + recurring automation`.

### Phase D — Additional verticals

The first Phase D vertical is **Communications**: governed email/messaging operations supporting inbox state, drafts, replies, outbound messages and follow-up workflows without a parallel uncontrolled execution path.

Communications sequence:
`D1 provider/adapter onboarding contract -> D2 registry/state model -> D3 read/health integration -> D4 policy/approval boundary -> D5 simulation/dry-run -> D6 controlled execution -> D7 reconciliation/retries -> D8 Command Centre operations`.

The second Phase D vertical is **Research**: governed search, retrieval, source normalization, evidence/citation tracking, research snapshots and later monitored research workflows that can feed other JARVIS verticals without bypassing their execution controls.

Research must preserve source provenance. A result is not trusted merely because a provider returned text. Stable source identity, source metadata, attribution/citation capability, timestamps and deterministic persisted research state are required before downstream automation can rely on it.

Research sequence:
`D9 provider/adapter onboarding contract -> D10 source/query/result registry + normalized state -> D11 read/search/fetch integration -> D12 evidence/provenance/confidence policy -> D13 research simulation/report assembly -> D14 controlled recurring/watch execution -> D15 reconciliation/freshness/retry -> D16 Research Command Centre operations`.

The third Phase D vertical is **Automation**: governed workflow orchestration across providers and existing JARVIS capabilities. Automation is treated as a high-risk cross-vertical capability because it can chain actions; therefore every workflow must remain inspectable, simulation-first, idempotent, permission-scoped and subject to the same policy/approval/kill-switch boundaries as the underlying verticals.

Automation sequence:
`D17 provider/adapter onboarding contract -> D18 workflow/trigger/action registry + normalized state -> D19 catalog/read/health integration -> D20 workflow policy/approval boundary -> D21 deterministic simulation/dry-run -> D22 controlled execution -> D23 reconciliation/retries/cancellation -> D24 Automation Command Centre operations`.

An Automation workflow may coordinate Trading, Content, Communications or Research only through those verticals' governed public boundaries. It may never call provider transports behind their policy/risk layers.

Future provider/channel verticals follow the same pattern after Automation.

No new vertical may bypass the shared AURON core simply because its provider API is easy to call.

## 6. Cross-vertical Command Centre requirements

The operational interface must ultimately provide:

- persistent command/text interaction field;
- system/capability health;
- simulation/live mode visibility;
- pending approvals;
- execution timeline and failures;
- Trading workspace with multi-account risk state;
- Content workspace with draft/schedule/publish state;
- Communications workspace with inbox/approval/execution state;
- Research workspace with queries, sources, evidence, freshness and watch state;
- Automation workspace with workflows, triggers, action plans, simulations, executions and reconciliation state;
- global and capability-specific kill switches;
- audit/evidence access.

A landing page or decorative footer must never replace the operational command field.

## 7. Definition of usable

A vertical is not considered usable merely because routes exist.

Minimum usable state requires:

1. provider/account connection health is observable;
2. persistent state survives process restart;
3. policy/risk gate executes before outbound action;
4. external action has idempotency and reconciliation;
5. operator can see success/failure in Command Centre;
6. kill/disable control exists;
7. integration tests cover failure and replay behavior;
8. live mode is deliberately enabled rather than being the default.

## 8. PR discipline

Each PR should implement one coherent layer, include tests, document dependencies and state the next layer. Before merge, verify CI and mergeability. After the user reports merge, verify GitHub before creating the next branch.

Do not generate endless successor generations after v21.523 unless a concrete architectural requirement demands it. Continue the planned phase sequence instead.

## 9. Current checkpoint

- Foundation successor loop: completed through AURON v21.523 / Generation Forty-Six continuity-expiry-renewal governance.
- Phase A core cutover: completed through A6 — end-to-end integration harness and core cutover certification.
- Phase B Trading architecture: completed through B10 — multi-account registry/state/signals/risk/allocation/guards, read-only + paper adapter, reconciliation/canary proof, controlled live-enablement boundary and Trading Command Centre operations.
- Trading live-provider execution remains deliberately disabled by default until a real provider transport is configured and all live gates are explicitly satisfied.
- Phase C Instagram Content Manager: completed through C8 — registry/calendar, lifecycle/version history, provider read-health, preview/approval, scheduler dry-run, controlled publish boundary, reconciliation/retries and Content Command Centre with explicit recurring-automation policy.
- Content provider writes remain disabled by default; recurring automation records policy/cadence only and never bypasses C4-C7 approval/reconciliation gates.
- Phase D Communications vertical: completed through D8 — provider onboarding, normalized account/channel/conversation state, read-only sync, approval policy, deterministic simulation, controlled execution boundary, reconciliation/retries and Communications Command Centre operations with persistent command field and kill-switch control.
- Communications outbound provider writes remain disabled by default; D8 exposes operational state and controls but does not silently execute recorded text commands.
- Phase D Research vertical: completed through D16 — provider onboarding, persistent query/source/result evidence registry, certified read/search/fetch integration, provenance/confidence admission policy, deterministic citation-bound report simulation, controlled watches, freshness/retry reconciliation and Research Command Centre operations with persistent command field and governed watch kill-switch control.
- Research unattended actions and all downstream Trading/Content/Communications execution remain disabled by default; D16 exposes operational visibility and controls but recorded commands are not executed directly.
- Current phase: Phase D — Automation vertical.
- Completed: D17 — Automation selected as the next vertical; provider/adapter onboarding contract requires simulation, inspectability, scoped permissions, idempotency, reconciliation support, identity/health/catalog verification and explicit operator approval, while automation execution and cross-vertical execution remain disabled; D18 — persistent provider-neutral workflow/trigger/action registry with normalized states, deterministic identities, integrity hashes, ordered actions and an explicit ready-for-simulation state while exposing no execution method; D19 — onboarding-certified provider catalog/read/health integration with normalized persistent catalog metadata, provider/catalog identity verification, simulation-capability enforcement and validation of registered D18 workflow actions against provider catalogs, while exposing no action execution; D20 — fail-closed workflow policy boundary with explicit operator approval, complete provider and target-vertical scopes, catalog revalidation, approval revocation and a per-workflow kill switch that defaults active. D20 can authorize simulation only; live execution remains explicitly blocked; D21 — deterministic persistent workflow simulation plans bound to the current D20 approval and workflow integrity hash, with ordered inspectable action plans, policy/workflow/action drift revalidation and zero provider writes or cross-vertical actions; D22 — controlled Automation execution boundary requiring successful D21 simulation, current D20 authorization, exact workflow/action integrity, explicit execution scope, operator enablement and clear D22 kill switch, with deterministic execution/action idempotency keys and a disabled-by-default execution transport.
- Next after D22 merge: D23 — Automation execution-result reconciliation, bounded retries and cancellation semantics before Automation Command Centre operations.

This section must be updated when phase boundaries or major activation milestones change so a new chat can recover the correct trajectory from the repository itself.
