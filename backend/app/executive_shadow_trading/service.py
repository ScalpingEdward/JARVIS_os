from collections import defaultdict
from datetime import datetime
from uuid import UUID

from .models import (
    AuditRecord,
    ExperimentCreate,
    ExperimentStatus,
    ExperimentStatusUpdate,
    ShadowOutcome,
    ShadowTrade,
    ShadowTradeCreate,
    ShadowTradeResult,
    ShadowTradingStatusResponse,
    StrategyExperiment,
)


class ExecutiveShadowTradingService:
    def __init__(self) -> None:
        self._experiments: dict[UUID, StrategyExperiment] = {}
        self._trades: dict[UUID, ShadowTrade] = {}
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> ShadowTradingStatusResponse:
        experiments = [e for e in self._experiments.values() if e.workspace_id == workspace_id]
        trades = [t for t in self._trades.values() if t.workspace_id == workspace_id]
        return ShadowTradingStatusResponse(
            workspace_id=workspace_id,
            experiments=len(experiments),
            shadow_trades=len(trades),
            unresolved_trades=sum(t.outcome == ShadowOutcome.pending for t in trades),
        )

    def create_experiment(self, payload: ExperimentCreate) -> StrategyExperiment:
        duplicate = any(
            e.workspace_id == payload.workspace_id and e.name.lower() == payload.name.lower()
            for e in self._experiments.values()
        )
        if duplicate:
            raise ValueError("Shadow-trading experiment already exists in workspace")
        if payload.baseline_experiment_id is not None:
            baseline = self._experiments.get(payload.baseline_experiment_id)
            if baseline is None or baseline.workspace_id != payload.workspace_id:
                raise ValueError("Baseline experiment not found in workspace")
        item = StrategyExperiment(**payload.model_dump())
        self._experiments[item.id] = item
        self._record(payload.workspace_id, "system", "experiment.created", item.id)
        return item

    def list_experiments(self, workspace_id: str) -> list[StrategyExperiment]:
        return [e for e in self._experiments.values() if e.workspace_id == workspace_id]

    def get_experiment(self, experiment_id: UUID, workspace_id: str) -> StrategyExperiment | None:
        item = self._experiments.get(experiment_id)
        return item if item and item.workspace_id == workspace_id else None

    def update_status(self, experiment_id: UUID, workspace_id: str, payload: ExperimentStatusUpdate) -> StrategyExperiment:
        item = self.get_experiment(experiment_id, workspace_id)
        if item is None:
            raise KeyError("Shadow-trading experiment not found")
        if payload.status == ExperimentStatus.completed and item.sample_size < item.minimum_sample_size:
            raise ValueError("Minimum sample size not reached")
        item.status = payload.status
        item.updated_at = datetime.utcnow()
        self._record(workspace_id, payload.actor_id, "experiment.status_updated", item.id, {"status": payload.status.value})
        return item

    def create_trade(self, payload: ShadowTradeCreate) -> ShadowTrade:
        experiment = self.get_experiment(payload.experiment_id, payload.workspace_id)
        if experiment is None:
            raise ValueError("Shadow-trading experiment not found in workspace")
        if experiment.status != ExperimentStatus.running:
            raise ValueError("Experiment must be running before predictions are recorded")
        if experiment.strategy_id != payload.strategy_id:
            raise ValueError("Trade strategy does not match experiment strategy")
        if experiment.permitted_account_profiles and payload.account_profile_id not in experiment.permitted_account_profiles:
            raise ValueError("Account profile is not permitted for this experiment")
        item = ShadowTrade(**payload.model_dump())
        self._trades[item.id] = item
        self._record(payload.workspace_id, "system", "shadow_trade.predicted", item.id)
        return item

    def list_trades(self, workspace_id: str, experiment_id: UUID | None = None) -> list[ShadowTrade]:
        return [
            t for t in self._trades.values()
            if t.workspace_id == workspace_id and (experiment_id is None or t.experiment_id == experiment_id)
        ]

    def resolve_trade(self, trade_id: UUID, workspace_id: str, result: ShadowTradeResult, actor_id: str) -> ShadowTrade:
        item = self._trades.get(trade_id)
        if item is None or item.workspace_id != workspace_id:
            raise KeyError("Shadow trade not found")
        if item.outcome != ShadowOutcome.pending:
            raise ValueError("Shadow trade has already been resolved")
        item.outcome = result.outcome
        item.result = result
        self._recalculate(item.experiment_id, workspace_id)
        self._record(workspace_id, actor_id, "shadow_trade.resolved", item.id, {"outcome": result.outcome.value})
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self._audit if a.workspace_id == workspace_id]

    def _recalculate(self, experiment_id: UUID, workspace_id: str) -> None:
        experiment = self.get_experiment(experiment_id, workspace_id)
        if experiment is None:
            return
        resolved = [
            t for t in self.list_trades(workspace_id, experiment_id)
            if t.result is not None and t.outcome in {ShadowOutcome.win, ShadowOutcome.loss, ShadowOutcome.breakeven}
        ]
        experiment.sample_size = len(resolved)
        if not resolved:
            return
        rs = [t.result.realized_r for t in resolved if t.result is not None]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r < 0]
        experiment.win_rate = round(len(wins) / len(rs), 4)
        experiment.average_r = round(sum(rs) / len(rs), 4)
        experiment.expectancy_r = experiment.average_r
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        experiment.profit_factor = round(gross_profit / gross_loss, 4) if gross_loss else None
        experiment.calibration_error = round(
            sum(abs(t.confidence - (1.0 if t.outcome == ShadowOutcome.win else 0.0)) for t in resolved) / len(resolved), 4
        )
        reasons: list[str] = []
        if experiment.sample_size < experiment.minimum_sample_size:
            reasons.append("minimum_sample_size_not_reached")
        if experiment.expectancy_r <= 0:
            reasons.append("non_positive_expectancy")
        if experiment.profit_factor is not None and experiment.profit_factor < 1.2:
            reasons.append("profit_factor_below_threshold")
        if experiment.calibration_error > 0.30:
            reasons.append("confidence_poorly_calibrated")
        experiment.rejection_reasons = reasons
        experiment.promotion_eligible = not reasons
        experiment.updated_at = datetime.utcnow()

    def _record(self, workspace_id: str, actor_id: str, action: str, entity_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity_id=entity_id,
            details=details or {},
        ))


executive_shadow_trading_service = ExecutiveShadowTradingService()
