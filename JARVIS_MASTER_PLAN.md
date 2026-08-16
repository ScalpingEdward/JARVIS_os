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

### Phase D — Additional verticals

Future modules (communications, research, automation, other channels/providers) reuse the same capability contract, policy gate, ledger, Command Centre and adapter architecture. They do not create parallel uncontrolled execution systems.

## 6. Cross-vertical Command Centre requirements

The operational interface must ultimately provide:

- persistent command/text interaction field;
- system/capability health;
- simulation/live mode visibility;
- pending approvals;
- execution timeline and failures;
- Trading workspace with multi-account risk state;
- Content workspace with draft/schedule/publish state;
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
- Current phase: Phase A — Integration readiness and core cutover.
- Completed: A1 — canonical roadmap + integration-readiness registry; A2 — unified capability/adapter contract; A3 — persistent execution/audit ledger + idempotency/reconciliation primitives; A4 — central policy gate with operator approval, environment mode, kill switches and capability scopes; A5 — Command Centre integration with persistent operational command field, real backend state, approvals and audit timeline.
- Next after A5 merge: A6 — end-to-end integration harness and core cutover certification.

This section must be updated when phase boundaries or major activation milestones change so a new chat can recover the correct trajectory from the repository itself.
