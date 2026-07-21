from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    LearningRecommendation,
    PerformanceLearningAudit,
    PerformanceLearningCreate,
    PerformanceLearningExecuteRequest,
    PerformanceLearningRecord,
    PerformanceLearningState,
    PerformanceLearningStatus,
    StrategyPerformance,
)


class PerformanceLearningMemoryService:
    def __init__(self) -> None:
        self._records: dict[UUID, PerformanceLearningRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[PerformanceLearningAudit] = []

    def create(self, payload: PerformanceLearningCreate) -> PerformanceLearningRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, strategies, recommendations, metrics = self._evaluate(payload)
        record = PerformanceLearningRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            strategies=strategies,
            recommendations=recommendations,
            **metrics,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, p: PerformanceLearningCreate):
        if p.upstream_risk_brain_blocked:
            return PerformanceLearningState.BLOCKED, "upstream Risk Brain hard block", [], [], self._empty_metrics()
        if not all(item.routed_by_v19_06 for item in p.outcomes):
            return PerformanceLearningState.ROUTE_EVIDENCE_REQUIRED, "v19.06 routed evidence required for every trade", [], [], self._empty_metrics()
        if len(p.outcomes) < p.min_sample_size:
            return PerformanceLearningState.SAMPLE_INSUFFICIENT, "minimum governed learning sample not reached", [], [], self._empty_metrics()

        grouped = defaultdict(list)
        for item in p.outcomes:
            grouped[item.strategy_id].append(item)

        strategies: list[StrategyPerformance] = []
        recommendations: list[LearningRecommendation] = []
        for strategy_id, trades in grouped.items():
            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl < 0]
            gross_profit = sum(t.pnl for t in wins)
            gross_loss = abs(sum(t.pnl for t in losses))
            expectancy = sum(t.realized_rr for t in trades) / len(trades)
            win_rate = len(wins) / len(trades) * 100
            confidence_error = sum(abs(t.signal_confidence - (100 if t.pnl > 0 else 0)) for t in trades) / len(trades)
            strategies.append(StrategyPerformance(
                strategy_id=strategy_id,
                trades=len(trades),
                wins=len(wins),
                losses=len(losses),
                win_rate_pct=round(win_rate, 2),
                net_pnl=round(sum(t.pnl for t in trades), 2),
                expectancy_r=round(expectancy, 4),
                profit_factor=round(gross_profit / gross_loss, 4) if gross_loss else 999.0,
                avg_slippage_bps=round(sum(t.slippage_bps for t in trades) / len(trades), 4),
                avg_holding_seconds=round(sum(t.holding_seconds for t in trades) / len(trades), 2),
                confidence_calibration_error=round(confidence_error, 2),
            ))
            if expectancy <= 0:
                recommendations.append(LearningRecommendation(strategy_id=strategy_id, action="pause", reason="non-positive realized expectancy", risk_multiplier=0))
            elif win_rate < p.baseline_win_rate_pct * (1 - p.degradation_threshold_pct / 100):
                recommendations.append(LearningRecommendation(strategy_id=strategy_id, action="reduce-risk", reason="win-rate degradation versus baseline", risk_multiplier=0.5))
            elif confidence_error > p.drift_threshold_pct:
                recommendations.append(LearningRecommendation(strategy_id=strategy_id, action="recalibrate", reason="signal confidence calibration drift", risk_multiplier=0.75))
            else:
                recommendations.append(LearningRecommendation(strategy_id=strategy_id, action="retain", reason="performance remains inside governed tolerance", risk_multiplier=1.0))

        pnls = [t.pnl for t in p.outcomes]
        gross_profit = sum(v for v in pnls if v > 0)
        gross_loss = abs(sum(v for v in pnls if v < 0))
        equity = peak = drawdown = 0.0
        for pnl in pnls:
            equity += pnl
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        win_rate = sum(v > 0 for v in pnls) / len(pnls) * 100
        expectancy = sum(t.realized_rr for t in p.outcomes) / len(p.outcomes)
        metrics = {
            "portfolio_win_rate_pct": round(win_rate, 2),
            "portfolio_expectancy_r": round(expectancy, 4),
            "portfolio_profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else 999.0,
            "max_drawdown": round(drawdown, 2),
        }
        if any(r.action == "pause" for r in recommendations):
            return PerformanceLearningState.DEGRADATION_DETECTED, "one or more strategies require immediate pause review", strategies, recommendations, metrics
        if any(r.action in {"reduce-risk", "recalibrate"} for r in recommendations):
            return PerformanceLearningState.REVIEW_REQUIRED, "performance drift requires governed review", strategies, recommendations, metrics
        return PerformanceLearningState.LEARNING_PENDING, "performance memory ready for human approval", strategies, recommendations, metrics

    def execute(self, record_id: UUID, workspace_id: str, request: PerformanceLearningExecuteRequest) -> PerformanceLearningRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("performance record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if not approved:
            raise ValueError("human approval required")
        if record.state in {PerformanceLearningState.BLOCKED, PerformanceLearningState.ROUTE_EVIDENCE_REQUIRED, PerformanceLearningState.SAMPLE_INSUFFICIENT, PerformanceLearningState.DATA_INVALID, PerformanceLearningState.FAILED}:
            raise ValueError("learning cannot be activated from current state")
        if request.action == "approve-learning":
            record.state, record.detail = PerformanceLearningState.LEARNING_APPROVED, "governed learning recommendations approved"
        elif request.action == "activate-memory":
            record.state, record.detail = PerformanceLearningState.MEMORY_ACTIVE, "performance memory activated for downstream decisions"
        else:
            raise ValueError("unsupported action")
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PerformanceLearningRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PerformanceLearningRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PerformanceLearningStatus:
        records = self.list_records(workspace_id)
        active = {PerformanceLearningState.LEARNING_APPROVED, PerformanceLearningState.MEMORY_ACTIVE, PerformanceLearningState.HEALTHY}
        blocked = {PerformanceLearningState.BLOCKED, PerformanceLearningState.ROUTE_EVIDENCE_REQUIRED, PerformanceLearningState.DATA_INVALID, PerformanceLearningState.FAILED}
        return PerformanceLearningStatus(workspace_id=workspace_id, total_records=len(records), active_records=sum(r.state in active for r in records), blocked_records=sum(r.state in blocked for r in records))

    def audit_records(self, workspace_id: str) -> list[PerformanceLearningAudit]:
        return [a for a in self._audit if a.workspace_id == workspace_id]

    @staticmethod
    def _empty_metrics() -> dict[str, float]:
        return {"portfolio_win_rate_pct": 0, "portfolio_expectancy_r": 0, "portfolio_profit_factor": 0, "max_drawdown": 0}

    def _log(self, record: PerformanceLearningRecord, actor_id: str, action: str) -> None:
        self._audit.append(PerformanceLearningAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))


performance_learning_memory_service = PerformanceLearningMemoryService()
