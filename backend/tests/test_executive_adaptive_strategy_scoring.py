import pytest

from app.executive_adaptive_strategy_scoring.models import (
    ScoreDecision,
    ScoringRunCreate,
    StrategyScoreInput,
)
from app.executive_adaptive_strategy_scoring.service import ExecutiveAdaptiveStrategyScoringService


def strategy(strategy_id: str, **overrides) -> StrategyScoreInput:
    payload = {
        "strategy_id": strategy_id,
        "strategy_version": "1.0",
        "regime_match": 0.9,
        "evidence_score": 0.85,
        "evidence_sample_size": 80,
        "shadow_score": 0.8,
        "profit_factor": 1.8,
        "expectancy_r": 0.35,
        "max_drawdown_pct": 5.0,
        "liquidity_score": 0.9,
        "volatility_fit": 0.85,
        "news_risk": 0.1,
        "spread_quality": 0.9,
        "recent_performance": 0.8,
        "stability_score": 0.8,
        "calibration_score": 0.85,
    }
    payload.update(overrides)
    return StrategyScoreInput(**payload)


def run_payload(strategies: list[StrategyScoreInput], workspace_id: str = "ws-1") -> ScoringRunCreate:
    return ScoringRunCreate(
        workspace_id=workspace_id,
        account_profile_id="ftmo-100k",
        symbol="XAUUSD",
        timeframe="M15",
        market_regime="strong_trend",
        actor_id="tester",
        strategies=strategies,
    )


def test_ranks_best_strategy_first() -> None:
    service = ExecutiveAdaptiveStrategyScoringService()
    result = service.create_run(run_payload([
        strategy("ict", is_champion=True),
        strategy("mean-reversion", regime_match=0.2, evidence_score=0.4),
    ]))
    assert result.results[0].strategy_id == "ict"
    assert result.results[0].rank == 1
    assert result.winner_strategy_id == "ict"


def test_small_sample_is_shadow_only() -> None:
    service = ExecutiveAdaptiveStrategyScoringService()
    result = service.create_run(run_payload([strategy("challenger", evidence_sample_size=5)]))
    assert result.results[0].decision == ScoreDecision.shadow_only


def test_news_risk_blocks_strategy() -> None:
    service = ExecutiveAdaptiveStrategyScoringService()
    result = service.create_run(run_payload([strategy("news-sensitive", news_risk=0.95)]))
    assert result.results[0].decision == ScoreDecision.blocked


def test_regime_block_is_respected() -> None:
    service = ExecutiveAdaptiveStrategyScoringService()
    result = service.create_run(run_payload([
        strategy("range", regime_permission=ScoreDecision.blocked)
    ]))
    assert result.results[0].decision == ScoreDecision.blocked


def test_workspace_isolation() -> None:
    service = ExecutiveAdaptiveStrategyScoringService()
    created = service.create_run(run_payload([strategy("ict")], workspace_id="alpha"))
    assert service.get(created.id, "beta") is None
    assert service.list_runs("beta") == []


def test_invalid_weights_are_rejected() -> None:
    from app.executive_adaptive_strategy_scoring.models import ScoringWeights

    with pytest.raises(ValueError):
        ScoringWeights(regime_match=0.9)
