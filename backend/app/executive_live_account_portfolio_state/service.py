from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AccountPortfolioAudit,
    AccountPortfolioRefreshRequest,
    AccountPortfolioSnapshot,
    AccountPortfolioSnapshotCreate,
    AccountPortfolioState,
    AccountPortfolioStatus,
)


class LiveAccountPortfolioStateService:
    def __init__(self) -> None:
        self._records: dict[UUID, AccountPortfolioSnapshot] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AccountPortfolioAudit] = []

    def create(self, payload: AccountPortfolioSnapshotCreate) -> AccountPortfolioSnapshot:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail = self._evaluate(payload)
        metrics = self._metrics(payload)
        record = AccountPortfolioSnapshot(state=state, detail=detail, request=payload, **metrics)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _metrics(self, p: AccountPortfolioSnapshotCreate) -> dict[str, float]:
        hwm = max(p.equity_high_watermark, p.equity, 0.01)
        day_start = max(p.daily_start_equity, 0.01)
        drawdown = max(0.0, (hwm - p.equity) / hwm * 100)
        daily_drawdown = max(0.0, (day_start - p.equity) / day_start * 100)
        heat = 0.0 if p.risk_budget_limit <= 0 else p.risk_budget_used / p.risk_budget_limit * 100
        buying_power = max(0.0, p.free_margin)
        penalties = min(100.0, drawdown * 8 + daily_drawdown * 6 + max(0.0, 250 - p.margin_level) / 5 + max(0.0, heat - 50) / 2)
        return {"current_drawdown_pct": round(drawdown, 4), "daily_drawdown_pct": round(daily_drawdown, 4), "portfolio_heat_pct": round(heat, 4), "buying_power": buying_power, "account_health_score": round(max(0.0, 100 - penalties), 2)}

    def _evaluate(self, p: AccountPortfolioSnapshotCreate) -> tuple[AccountPortfolioState, str]:
        if p.risk_brain_blocked:
            return AccountPortfolioState.BLOCKED, "Risk Brain hard block"
        if not p.reconciliation_complete:
            return AccountPortfolioState.SYNCHRONIZATION_REQUIRED, "v19.02 reconciliation-complete evidence required"
        if not p.account_risk_approved:
            return AccountPortfolioState.BLOCKED, "account-risk approval required"
        if not p.prop_rules_approved:
            return AccountPortfolioState.BLOCKED, "prop-rule approval required"
        m = self._metrics(p)
        max_loss = max(0.0, p.balance - p.equity)
        daily_loss = max(0.0, -p.daily_pl)
        if (p.max_loss_limit and max_loss >= p.max_loss_limit) or (p.daily_loss_limit and daily_loss >= p.daily_loss_limit):
            return AccountPortfolioState.PROP_LIMIT_BREACHED, "prop-firm loss limit breached"
        if p.margin_level <= p.margin_critical_level or m["current_drawdown_pct"] >= p.drawdown_critical_pct:
            return AccountPortfolioState.DRAWDOWN_CRITICAL, "critical margin or drawdown threshold reached"
        if p.margin_level <= p.margin_warning_level:
            return AccountPortfolioState.MARGIN_WARNING, "margin warning threshold reached"
        if m["current_drawdown_pct"] >= p.drawdown_warning_pct:
            return AccountPortfolioState.DRAWDOWN_WARNING, "drawdown warning threshold reached"
        if (p.daily_loss_limit and daily_loss >= p.daily_loss_limit * p.prop_warning_ratio) or (p.max_loss_limit and max_loss >= p.max_loss_limit * p.prop_warning_ratio):
            return AccountPortfolioState.PROP_LIMIT_WARNING, "approaching prop-firm loss limit"
        return AccountPortfolioState.HEALTHY, "live account and portfolio state healthy"

    def refresh(self, record_id: UUID, workspace_id: str, request: AccountPortfolioRefreshRequest) -> AccountPortfolioSnapshot:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("snapshot not found")
        if record.state in {AccountPortfolioState.DRAWDOWN_CRITICAL, AccountPortfolioState.PROP_LIMIT_BREACHED, AccountPortfolioState.RECOVERY_REQUIRED} and not request.human_approved:
            raise ValueError("human approval required for critical recovery refresh")
        state, detail = self._evaluate(record.request)
        metrics = self._metrics(record.request)
        record.state, record.detail = state, detail
        for key, value in metrics.items():
            setattr(record, key, value)
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> AccountPortfolioSnapshot | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[AccountPortfolioSnapshot]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> AccountPortfolioStatus:
        items = self.list_records(workspace_id)
        critical = {AccountPortfolioState.DRAWDOWN_CRITICAL, AccountPortfolioState.PROP_LIMIT_BREACHED, AccountPortfolioState.ACCOUNT_UNHEALTHY, AccountPortfolioState.FAILED}
        return AccountPortfolioStatus(workspace_id=workspace_id, total_records=len(items), healthy_records=sum(r.state == AccountPortfolioState.HEALTHY for r in items), critical_records=sum(r.state in critical for r in items))

    def audit_records(self, workspace_id: str) -> list[AccountPortfolioAudit]:
        return [a for a in self._audit if a.workspace_id == workspace_id]

    def _log(self, record: AccountPortfolioSnapshot, actor_id: str, action: str) -> None:
        self._audit.append(AccountPortfolioAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))


live_account_portfolio_state_service = LiveAccountPortfolioStateService()
