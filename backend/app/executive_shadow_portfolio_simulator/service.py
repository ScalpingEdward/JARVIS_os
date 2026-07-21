from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ShadowPortfolioAudit,
    ShadowPortfolioCreate,
    ShadowPortfolioExecuteRequest,
    ShadowPortfolioRecord,
    ShadowPortfolioState,
    ShadowPortfolioStatus,
    ShadowStrategyResult,
)


class ShadowPortfolioSimulatorService:
    def __init__(self) -> None:
        self._records: dict[UUID, ShadowPortfolioRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[ShadowPortfolioAudit] = []

    def create(self, payload: ShadowPortfolioCreate) -> ShadowPortfolioRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, metrics, strategies = self._evaluate(payload)
        record = ShadowPortfolioRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            strategies=strategies,
            **metrics,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, p: ShadowPortfolioCreate):
        empty = self._empty_metrics(p.initial_equity)
        if p.upstream_risk_brain_blocked:
            return ShadowPortfolioState.BLOCKED, "upstream Risk Brain hard block", empty, []
        if not p.account_risk_approved or not p.prop_rules_approved:
            return ShadowPortfolioState.BLOCKED, "account-risk and prop-rule approval required", empty, []
        if not p.market_permission_approved:
            return ShadowPortfolioState.MARKET_PERMISSION_REQUIRED, "v19.08 trade-allowed evidence required", empty, []
        if not all(t.market_allowed_by_v19_08 and t.routed_by_v19_06 for t in p.trades):
            return ShadowPortfolioState.MARKET_PERMISSION_REQUIRED, "all shadow trades require v19.06 routing and v19.08 market permission", empty, []
        if len(p.trades) < p.min_sample_size:
            return ShadowPortfolioState.SAMPLE_INSUFFICIENT, "minimum shadow sample not reached", empty, []

        grouped = defaultdict(list)
        for trade in p.trades:
            grouped[trade.strategy_id].append(trade)

        strategy_results: list[ShadowStrategyResult] = []
        total_breaches = 0
        for strategy_id, trades in grouped.items():
            strategy_result = self._calculate_strategy(strategy_id, trades, p.initial_equity, p.max_total_drawdown_pct)
            total_breaches += strategy_result.risk_breaches
            strategy_results.append(strategy_result)

        pnls = [t.pnl for t in p.trades]
        wins = [v for v in pnls if v > 0]
        losses = [v for v in pnls if v < 0]
        equity = p.initial_equity
        peak = equity
        max_drawdown = 0.0
        worst_daily_loss = 0.0
        for pnl in pnls:
            equity += pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            if pnl < 0:
                worst_daily_loss = max(worst_daily_loss, abs(pnl) / p.initial_equity * 100)
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        expectancy = sum(t.realized_rr for t in p.trades) / len(p.trades)
        profit_factor = gross_profit / gross_loss if gross_loss else 999.0
        avg_slippage = sum(t.slippage_bps for t in p.trades) / len(p.trades)
        max_drawdown_pct = max_drawdown / p.initial_equity * 100
        total_breaches += int(worst_daily_loss > p.max_daily_loss_pct)
        total_breaches += int(max_drawdown_pct > p.max_total_drawdown_pct)
        metrics = {
            "ending_equity": round(equity, 2),
            "net_pnl": round(sum(pnls), 2),
            "win_rate_pct": round(len(wins) / len(pnls) * 100, 2),
            "expectancy_r": round(expectancy, 4),
            "profit_factor": round(profit_factor, 4),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "max_daily_loss_pct_observed": round(worst_daily_loss, 4),
            "avg_slippage_bps": round(avg_slippage, 4),
            "risk_breaches": total_breaches,
        }
        if total_breaches:
            return ShadowPortfolioState.BREACH_DETECTED, "shadow portfolio breached governed risk limits", metrics, strategy_results
        if expectancy < p.min_expectancy_r or profit_factor < p.min_profit_factor or avg_slippage > p.max_slippage_bps:
            return ShadowPortfolioState.DEGRADATION_DETECTED, "shadow performance below promotion thresholds", metrics, strategy_results
        if len(p.trades) >= p.promotion_min_trades:
            return ShadowPortfolioState.PROMOTION_CANDIDATE, "shadow portfolio qualifies for governed promotion review", metrics, strategy_results
        return ShadowPortfolioState.SIMULATION_READY, "shadow simulation completed and ready for approval", metrics, strategy_results

    @staticmethod
    def _calculate_strategy(strategy_id, trades, initial_equity, max_dd_pct):
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        equity = peak = initial_equity
        drawdown = 0.0
        for trade in trades:
            equity += trade.pnl
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        expectancy = sum(t.realized_rr for t in trades) / len(trades)
        profit_factor = gross_profit / gross_loss if gross_loss else 999.0
        avg_slippage = sum(t.slippage_bps for t in trades) / len(trades)
        breaches = int(drawdown / initial_equity * 100 > max_dd_pct)
        recommendation = "retain"
        if breaches or expectancy <= 0:
            recommendation = "reject"
        elif profit_factor < 1.2 or avg_slippage > 8:
            recommendation = "recalibrate"
        return ShadowStrategyResult(
            strategy_id=strategy_id,
            trades=len(trades),
            wins=len(wins),
            losses=len(losses),
            win_rate_pct=round(len(wins) / len(trades) * 100, 2),
            net_pnl=round(sum(t.pnl for t in trades), 2),
            expectancy_r=round(expectancy, 4),
            profit_factor=round(profit_factor, 4),
            max_drawdown=round(drawdown, 2),
            avg_slippage_bps=round(avg_slippage, 4),
            risk_breaches=breaches,
            recommendation=recommendation,
        )

    def execute(self, record_id: UUID, workspace_id: str, request: ShadowPortfolioExecuteRequest) -> ShadowPortfolioRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("shadow portfolio record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if not approved:
            raise ValueError("human approval required")
        if record.state in {ShadowPortfolioState.BLOCKED, ShadowPortfolioState.MARKET_PERMISSION_REQUIRED, ShadowPortfolioState.SAMPLE_INSUFFICIENT, ShadowPortfolioState.BREACH_DETECTED, ShadowPortfolioState.FAILED}:
            raise ValueError("shadow portfolio cannot be activated from current state")
        if request.action == "activate-shadow":
            record.state, record.detail = ShadowPortfolioState.SHADOW_ACTIVE, "approved shadow portfolio activated"
        elif request.action == "promote":
            if record.state != ShadowPortfolioState.PROMOTION_CANDIDATE:
                raise ValueError("portfolio is not a promotion candidate")
            record.state, record.detail = ShadowPortfolioState.MONITORING, "promotion approved under monitored rollout"
        elif request.action == "reject":
            record.state, record.detail = ShadowPortfolioState.REJECTED, "shadow portfolio rejected by human review"
        else:
            raise ValueError("unsupported action")
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ShadowPortfolioRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ShadowPortfolioRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ShadowPortfolioStatus:
        records = self.list_records(workspace_id)
        active = {ShadowPortfolioState.SHADOW_ACTIVE, ShadowPortfolioState.PROMOTION_CANDIDATE, ShadowPortfolioState.MONITORING}
        blocked = {ShadowPortfolioState.BLOCKED, ShadowPortfolioState.BREACH_DETECTED, ShadowPortfolioState.REJECTED, ShadowPortfolioState.FAILED}
        return ShadowPortfolioStatus(workspace_id=workspace_id, total_records=len(records), active_records=sum(r.state in active for r in records), blocked_records=sum(r.state in blocked for r in records))

    def audit_records(self, workspace_id: str) -> list[ShadowPortfolioAudit]:
        return [a for a in self._audit if a.workspace_id == workspace_id]

    @staticmethod
    def _empty_metrics(initial_equity: float) -> dict[str, float | int]:
        return {"ending_equity": initial_equity, "net_pnl": 0, "win_rate_pct": 0, "expectancy_r": 0, "profit_factor": 0, "max_drawdown": 0, "max_drawdown_pct": 0, "max_daily_loss_pct_observed": 0, "avg_slippage_bps": 0, "risk_breaches": 0}

    def _log(self, record: ShadowPortfolioRecord, actor_id: str, action: str) -> None:
        self._audit.append(ShadowPortfolioAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))


shadow_portfolio_simulator_service = ShadowPortfolioSimulatorService()
