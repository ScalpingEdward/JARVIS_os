from __future__ import annotations

from collections import defaultdict

from .models import (
    AuditEvent, LiveAlphaAction, LiveAlphaCreate, LiveAlphaRecord, LiveAlphaState, utcnow,
)


class GovernanceError(ValueError):
    pass


class LiveAlphaGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, LiveAlphaRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: LiveAlphaCreate) -> LiveAlphaRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = LiveAlphaRecord(
            **payload.model_dump(),
            recommended_capital=payload.deployed_capital,
            state=LiveAlphaState.BLOCKED if payload.risk_brain_blocked else LiveAlphaState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[LiveAlphaRecord]:
        return [r for r in self.records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> LiveAlphaRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: LiveAlphaAction) -> LiveAlphaRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({LiveAlphaState.DRAFT}, LiveAlphaState.EVIDENCE_READY),
            "analyze": ({LiveAlphaState.EVIDENCE_READY}, LiveAlphaState.ANALYZED),
            "request-review": ({LiveAlphaState.ANALYZED}, LiveAlphaState.REVIEW_REQUIRED),
            "approve": ({LiveAlphaState.REVIEW_REQUIRED}, LiveAlphaState.APPROVED),
            "start-monitoring": ({LiveAlphaState.APPROVED}, LiveAlphaState.MONITORING),
            "reduce-capital": ({LiveAlphaState.DEGRADED, LiveAlphaState.CAPITAL_WARNING, LiveAlphaState.ESCALATED}, LiveAlphaState.CAPITAL_REDUCTION),
            "begin-recovery": ({LiveAlphaState.CAPITAL_REDUCTION, LiveAlphaState.SUSPENDED}, LiveAlphaState.RECOVERY),
            "revalidate": ({LiveAlphaState.RECOVERY}, LiveAlphaState.REVALIDATED),
            "escalate": ({LiveAlphaState.MONITORING, LiveAlphaState.HEALTHY, LiveAlphaState.DEGRADED, LiveAlphaState.CAPITAL_WARNING}, LiveAlphaState.ESCALATED),
            "suspend": ({LiveAlphaState.MONITORING, LiveAlphaState.HEALTHY, LiveAlphaState.DEGRADED, LiveAlphaState.CAPITAL_WARNING, LiveAlphaState.ESCALATED}, LiveAlphaState.SUSPENDED),
            "resume": ({LiveAlphaState.SUSPENDED}, LiveAlphaState.MONITORING),
            "retire": ({LiveAlphaState.ESCALATED, LiveAlphaState.SUSPENDED, LiveAlphaState.CAPITAL_REDUCTION}, LiveAlphaState.RETIRED),
            "revoke": (set(LiveAlphaState) - {LiveAlphaState.ARCHIVED}, LiveAlphaState.REVOKED),
            "archive": ({LiveAlphaState.RETIRED, LiveAlphaState.REVOKED, LiveAlphaState.REVALIDATED}, LiveAlphaState.ARCHIVED),
        }

        if command.action == "approve":
            if not command.approval_token:
                raise GovernanceError("approval_token required")
            if command.approval_token in self.approval_tokens:
                raise GovernanceError("approval_token replay detected")
            self.approval_tokens.add(command.approval_token)

        if command.action in {"start-monitoring", "reduce-capital", "retire"}:
            if not command.operation_receipt:
                raise GovernanceError("operation_receipt required")
            if command.operation_receipt in self.operation_receipts:
                raise GovernanceError("operation_receipt replay detected")
            self.operation_receipts.add(command.operation_receipt)

        if command.action == "observe":
            if record.state not in {LiveAlphaState.MONITORING, LiveAlphaState.HEALTHY, LiveAlphaState.DEGRADED, LiveAlphaState.CAPITAL_WARNING, LiveAlphaState.RECOVERY}:
                raise GovernanceError("observe not allowed in current state")
            if not command.snapshot:
                raise GovernanceError("snapshot required")
            record.snapshots.append(command.snapshot)
            self._evaluate(record)
            if record.violations:
                record.healthy_cycles = 0
                record.state = LiveAlphaState.CAPITAL_WARNING if record.health_score >= record.policy.warning_health_score else LiveAlphaState.ESCALATED
            else:
                record.healthy_cycles += 1
                record.state = LiveAlphaState.HEALTHY if record.healthy_cycles >= record.policy.healthy_cycles_required else LiveAlphaState.MONITORING
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            record.state = target
            if command.action == "reduce-capital":
                record.recommended_capital = round(record.deployed_capital * 0.5, 2)

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: LiveAlphaRecord) -> None:
        snap = record.snapshots[-1]
        baseline = max(abs(snap.rolling_alpha_90d_pct), 0.01)
        record.alpha_decay_pct = max(0.0, (snap.rolling_alpha_90d_pct - snap.rolling_alpha_7d_pct) / baseline * 100)
        profitability = min(100.0, max(0.0, 50 + snap.rolling_alpha_30d_pct * 5))
        drawdown = max(0.0, 100 - (snap.drawdown_pct / record.policy.maximum_drawdown_pct) * 100)
        quality = min(100.0, max(0.0, 40 + snap.sharpe * 20 + (snap.profit_factor - 1) * 30))
        stability = max(0.0, 100 - snap.volatility_pct * 4)
        record.health_score = round(
            profitability * 0.25 + drawdown * 0.25 + quality * 0.2 + stability * 0.1 + snap.liquidity_score * 0.1 + snap.confidence * 100 * 0.1,
            2,
        )
        violations: list[str] = []
        if snap.drawdown_pct > record.policy.maximum_drawdown_pct: violations.append("maximum_drawdown_exceeded")
        if snap.sharpe < record.policy.minimum_sharpe: violations.append("sharpe_below_minimum")
        if snap.profit_factor < record.policy.minimum_profit_factor: violations.append("profit_factor_below_minimum")
        if snap.liquidity_score < record.policy.minimum_liquidity_score: violations.append("liquidity_below_minimum")
        if record.alpha_decay_pct > record.policy.alpha_decay_tolerance_pct: violations.append("alpha_decay_detected")
        if record.health_score < record.policy.minimum_health_score: violations.append("health_score_below_minimum")
        record.violations = violations

    def _audit(self, record: LiveAlphaRecord, action: str, actor: str, before: LiveAlphaState, after: LiveAlphaState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = LiveAlphaGovernanceService()
