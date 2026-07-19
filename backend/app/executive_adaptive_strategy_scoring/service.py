from uuid import UUID

from .models import (
    AdaptiveScoringStatusResponse,
    AuditRecord,
    ConfidenceBand,
    ScoreBreakdown,
    ScoreDecision,
    ScoringRun,
    ScoringRunCreate,
    StrategyScoreInput,
    StrategyScoreResult,
)


class ExecutiveAdaptiveStrategyScoringService:
    def __init__(self) -> None:
        self._runs: dict[UUID, ScoringRun] = {}
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> AdaptiveScoringStatusResponse:
        count = sum(1 for item in self._runs.values() if item.workspace_id == workspace_id)
        return AdaptiveScoringStatusResponse(workspace_id=workspace_id, scoring_runs=count)

    def create_run(self, payload: ScoringRunCreate) -> ScoringRun:
        results = [self._score_strategy(item, payload) for item in payload.strategies]
        results.sort(key=lambda item: item.final_score, reverse=True)
        for rank, result in enumerate(results, start=1):
            result.rank = rank
        winner = next((item.strategy_id for item in results if item.decision == ScoreDecision.eligible), None)
        run = ScoringRun(
            workspace_id=payload.workspace_id,
            account_profile_id=payload.account_profile_id,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe.upper(),
            market_regime=payload.market_regime,
            actor_id=payload.actor_id,
            weights=payload.weights,
            results=results,
            winner_strategy_id=winner,
        )
        self._runs[run.id] = run
        self._audit.append(AuditRecord(
            workspace_id=payload.workspace_id,
            actor_id=payload.actor_id,
            action="adaptive_strategy_scoring_run_created",
            entity_id=run.id,
            details={"winner_strategy_id": winner, "strategy_count": len(results)},
        ))
        return run

    def list_runs(self, workspace_id: str, account_profile_id: str | None = None) -> list[ScoringRun]:
        items = [item for item in self._runs.values() if item.workspace_id == workspace_id]
        if account_profile_id is not None:
            items = [item for item in items if item.account_profile_id == account_profile_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, run_id: UUID, workspace_id: str) -> ScoringRun | None:
        item = self._runs.get(run_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _score_strategy(self, item: StrategyScoreInput, payload: ScoringRunCreate) -> StrategyScoreResult:
        reasons: list[str] = []
        evidence_reliability = min(1.0, item.evidence_sample_size / max(payload.minimum_evidence_sample, 1))
        evidence_component = item.evidence_score * evidence_reliability
        champion_component = 1.0 if item.is_champion else 0.5
        drawdown_quality = max(0.0, 1.0 - item.max_drawdown_pct / max(payload.maximum_drawdown_pct, 0.01))
        profit_factor_quality = min(1.0, item.profit_factor / 2.0)
        expectancy_quality = min(1.0, max(0.0, (item.expectancy_r + 0.5) / 1.5))
        risk_quality = (drawdown_quality * 0.5) + (profit_factor_quality * 0.25) + (expectancy_quality * 0.25)
        market_quality = (
            item.liquidity_score * 0.35
            + item.volatility_fit * 0.25
            + item.spread_quality * 0.25
            + (1.0 - item.news_risk) * 0.15
        )
        recency_stability = (item.recent_performance + item.stability_score) / 2
        components = ScoreBreakdown(
            regime_match=round(item.regime_match * 100, 2),
            evidence=round(evidence_component * 100, 2),
            shadow_performance=round(item.shadow_score * 100, 2),
            champion_status=round(champion_component * 100, 2),
            risk_quality=round(risk_quality * 100, 2),
            market_quality=round(market_quality * 100, 2),
            recency_stability=round(recency_stability * 100, 2),
            calibration=round(item.calibration_score * 100, 2),
        )
        weights = payload.weights
        final_score = round(
            components.regime_match * weights.regime_match
            + components.evidence * weights.evidence
            + components.shadow_performance * weights.shadow_performance
            + components.champion_status * weights.champion_status
            + components.risk_quality * weights.risk_quality
            + components.market_quality * weights.market_quality
            + components.recency_stability * weights.recency_stability
            + components.calibration * weights.calibration,
            2,
        )
        decision = ScoreDecision.eligible
        if item.regime_permission == ScoreDecision.blocked:
            decision = ScoreDecision.blocked
            reasons.append("Strategy is blocked by market-regime permission")
        elif item.news_risk > payload.maximum_news_risk:
            decision = ScoreDecision.blocked
            reasons.append("News risk exceeds governed maximum")
        elif item.max_drawdown_pct > payload.maximum_drawdown_pct:
            decision = ScoreDecision.blocked
            reasons.append("Drawdown exceeds governed maximum")
        elif item.regime_permission == ScoreDecision.shadow_only:
            decision = ScoreDecision.shadow_only
            reasons.append("Market-regime permission restricts strategy to shadow mode")
        elif item.evidence_sample_size < payload.minimum_evidence_sample:
            decision = ScoreDecision.shadow_only
            reasons.append("Evidence sample is below the governed minimum")
        elif final_score < payload.minimum_shadow_score:
            decision = ScoreDecision.blocked
            reasons.append("Adaptive score is below the minimum shadow threshold")
        elif final_score < payload.minimum_eligible_score:
            decision = ScoreDecision.shadow_only
            reasons.append("Adaptive score supports shadow testing but not eligibility")
        else:
            reasons.append("Adaptive score and safety gates support eligibility")
        confidence = self._confidence_band(item.evidence_sample_size, item.calibration_score, item.stability_score)
        return StrategyScoreResult(
            strategy_id=item.strategy_id,
            strategy_version=item.strategy_version,
            final_score=final_score,
            decision=decision,
            confidence_band=confidence,
            breakdown=components,
            reasons=reasons,
        )

    @staticmethod
    def _confidence_band(sample_size: int, calibration: float, stability: float) -> ConfidenceBand:
        score = min(1.0, sample_size / 100) * 0.5 + calibration * 0.25 + stability * 0.25
        if score >= 0.85:
            return ConfidenceBand.very_high
        if score >= 0.65:
            return ConfidenceBand.high
        if score >= 0.4:
            return ConfidenceBand.moderate
        return ConfidenceBand.low


executive_adaptive_strategy_scoring_service = ExecutiveAdaptiveStrategyScoringService()
