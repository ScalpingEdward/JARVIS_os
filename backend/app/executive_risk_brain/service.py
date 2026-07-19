from collections import defaultdict
from uuid import UUID

from .models import (
    AuditRecord,
    RiskBrainRun,
    RiskBrainRunCreate,
    RiskMetrics,
    RiskState,
    RiskTrend,
    StrategyRiskDecision,
)


class ExecutiveRiskBrainService:
    def __init__(self) -> None:
        self._runs: dict[UUID, RiskBrainRun] = {}
        self._audit: list[AuditRecord] = []
        self._source_refs: set[tuple[str, str]] = set()

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    def status(self, workspace_id: str):
        from .models import RiskBrainStatusResponse

        count = sum(1 for item in self._runs.values() if item.workspace_id == workspace_id)
        return RiskBrainStatusResponse(workspace_id=workspace_id, runs=count)

    def create(self, payload: RiskBrainRunCreate) -> RiskBrainRun:
        if payload.source_reference:
            key = (payload.workspace_id, payload.source_reference)
            if key in self._source_refs:
                raise ValueError("Duplicate risk-brain source reference")

        c = payload.components
        weights = {
            "portfolio_heat": 0.16,
            "drawdown_risk": 0.16,
            "correlation_risk": 0.10,
            "concentration_risk": 0.09,
            "liquidity_risk": 0.08,
            "volatility_risk": 0.08,
            "news_risk": 0.10,
            "tail_risk": 0.09,
            "model_risk": 0.05,
            "operational_risk": 0.04,
            "confidence_risk": 0.05,
        }
        global_score = self._clamp(sum(getattr(c, name) * weight for name, weight in weights.items()))

        previous = payload.previous_global_risk_score
        velocity = 0.0 if previous is None else round(global_score - previous, 2)
        if velocity >= 12:
            trend = RiskTrend.accelerating
        elif velocity >= 4:
            trend = RiskTrend.deteriorating
        elif velocity <= -4:
            trend = RiskTrend.improving
        else:
            trend = RiskTrend.stable

        forecast = self._clamp(global_score + max(-10.0, min(15.0, velocity * 0.6)))
        stability = self._clamp(100 - (c.volatility_risk * 0.35 + c.model_risk * 0.25 + c.operational_risk * 0.20 + c.confidence_risk * 0.20))
        survival = self._clamp(100 - (c.tail_risk * 0.35 + c.drawdown_risk * 0.35 + c.liquidity_risk * 0.20 + c.portfolio_heat * 0.10))
        recovery = self._clamp(100 - (c.drawdown_risk * 0.45 + c.liquidity_risk * 0.25 + c.volatility_risk * 0.15 + c.confidence_risk * 0.15))
        preservation = self._clamp(100 - (global_score * 0.70 + c.tail_risk * 0.15 + c.portfolio_heat * 0.15))

        reasons: list[str] = []
        thresholds = payload.thresholds
        hard_block = c.portfolio_heat >= thresholds.max_portfolio_heat and c.drawdown_risk >= thresholds.max_drawdown_risk
        if c.news_risk >= thresholds.max_news_risk:
            reasons.append("News risk exceeded hard limit")
        if c.portfolio_heat >= thresholds.max_portfolio_heat:
            reasons.append("Portfolio heat exceeded limit")
        if c.drawdown_risk >= thresholds.max_drawdown_risk:
            reasons.append("Drawdown risk exceeded limit")
        if c.correlation_risk >= 75:
            reasons.append("Portfolio correlation is elevated")
        if c.tail_risk >= 75:
            reasons.append("Tail-risk protection is required")
        if trend == RiskTrend.accelerating:
            reasons.append("Risk deterioration is accelerating")

        if hard_block or global_score >= thresholds.blocked_score:
            global_state = RiskState.blocked
        elif c.news_risk >= thresholds.max_news_risk or global_score >= thresholds.frozen_score:
            global_state = RiskState.frozen
        elif global_score >= thresholds.reduced_score:
            global_state = RiskState.reduced
        else:
            global_state = RiskState.normal
        if not reasons:
            reasons.append("Risk remains within governed thresholds")

        decisions: list[StrategyRiskDecision] = []
        symbol_weights: dict[str, float] = defaultdict(float)
        cluster_weights: dict[str, float] = defaultdict(float)
        for strategy in payload.strategies:
            symbol_weights[strategy.symbol] += strategy.current_weight
            cluster_weights[strategy.asset_cluster] += strategy.current_weight

        for strategy in payload.strategies:
            strategy_score = self._clamp(
                strategy.risk_contribution * 0.30
                + strategy.drawdown_pct * 0.25
                + max(0.0, strategy.correlation_to_portfolio) * 100 * 0.20
                + (100 - strategy.confidence) * 0.15
                + (100 - strategy.adaptive_score) * 0.10
            )
            strategy_reasons: list[str] = []
            if global_state == RiskState.blocked:
                state = RiskState.blocked
                multiplier = 0.0
                strategy_reasons.append("Global risk state blocks all strategy exposure")
            elif strategy.risk_contribution >= thresholds.max_strategy_risk_contribution:
                state = RiskState.frozen
                multiplier = 0.0
                strategy_reasons.append("Strategy risk contribution exceeded limit")
            elif strategy.correlation_to_portfolio >= 0.85 or symbol_weights[strategy.symbol] > 0.55 or cluster_weights[strategy.asset_cluster] > 0.70:
                state = RiskState.reduced
                multiplier = 0.5
                strategy_reasons.append("Correlation or concentration requires reduced exposure")
            elif strategy.confidence < 45 or strategy.adaptive_score < 50:
                state = RiskState.frozen
                multiplier = 0.0
                strategy_reasons.append("Strategy confidence or adaptive score is insufficient")
            elif global_state == RiskState.frozen:
                state = RiskState.frozen
                multiplier = 0.0
                strategy_reasons.append("Global frozen state prevents new exposure")
            elif global_state == RiskState.reduced or strategy_score >= thresholds.reduced_score:
                state = RiskState.reduced
                multiplier = 0.5
                strategy_reasons.append("Risk budget requires reduced exposure")
            else:
                state = RiskState.normal
                multiplier = 1.0
                strategy_reasons.append("Strategy remains within governed risk limits")
            decisions.append(
                StrategyRiskDecision(
                    strategy_id=strategy.strategy_id,
                    state=state,
                    risk_score=strategy_score,
                    recommended_weight_multiplier=multiplier,
                    reasons=strategy_reasons,
                )
            )

        run = RiskBrainRun(
            workspace_id=payload.workspace_id,
            account_profile_id=payload.account_profile_id,
            actor_id=payload.actor_id,
            source_portfolio_run_id=payload.source_portfolio_run_id,
            components=payload.components,
            strategy_decisions=decisions,
            metrics=RiskMetrics(
                global_risk_score=global_score,
                heat_score=self._clamp(c.portfolio_heat),
                stability_score=stability,
                survival_score=survival,
                recovery_score=recovery,
                capital_preservation_score=preservation,
                risk_velocity=velocity,
                forecast_risk_score=forecast,
                risk_trend=trend,
            ),
            global_state=global_state,
            reasons=reasons,
            source_reference=payload.source_reference,
        )
        self._runs[run.id] = run
        if payload.source_reference:
            self._source_refs.add((payload.workspace_id, payload.source_reference))
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                action="risk_brain_run_created",
                entity_id=run.id,
                details={"global_state": global_state.value, "global_risk_score": global_score},
            )
        )
        return run

    def get(self, run_id: UUID, workspace_id: str) -> RiskBrainRun | None:
        run = self._runs.get(run_id)
        return run if run and run.workspace_id == workspace_id else None

    def list_runs(self, workspace_id: str, account_profile_id: str | None = None) -> list[RiskBrainRun]:
        runs = [item for item in self._runs.values() if item.workspace_id == workspace_id]
        if account_profile_id:
            runs = [item for item in runs if item.account_profile_id == account_profile_id]
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_risk_brain_service = ExecutiveRiskBrainService()
