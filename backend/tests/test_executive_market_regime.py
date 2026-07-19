from app.executive_market_regime.models import (
    MarketRegime,
    RegimeAssessmentCreate,
    RegimeDecision,
    RegimeFeatureSnapshot,
    RegimeStrategyEvaluationRequest,
    StrategyRegimeRule,
)
from app.executive_market_regime.service import ExecutiveMarketRegimeService


def payload(workspace_id: str = "ws-1", account_profile_id: str = "ftmo-100k") -> RegimeAssessmentCreate:
    return RegimeAssessmentCreate(
        workspace_id=workspace_id,
        account_profile_id=account_profile_id,
        symbol="XAUUSD",
        timeframe="M15",
        actor_id="jarvis",
        features=RegimeFeatureSnapshot(
            trend_strength=0.92,
            volatility_percentile=0.72,
            range_efficiency=0.18,
            compression_score=0.12,
            expansion_score=0.78,
            liquidity_score=0.90,
            directional_imbalance=0.84,
            volume_confirmation=0.88,
            news_risk=0.10,
            session="london_open",
            killzone_active=True,
        ),
    )


def test_detects_directional_regime_and_allows_trading() -> None:
    service = ExecutiveMarketRegimeService()
    assessment = service.assess(payload())
    assert assessment.primary_regime == MarketRegime.strong_trend
    assert assessment.tradability == RegimeDecision.allow
    assert assessment.confidence >= 0.80


def test_low_liquidity_blocks_all_strategies() -> None:
    service = ExecutiveMarketRegimeService()
    request = payload()
    request.features.liquidity_score = 0.10
    assessment = service.assess(request)
    result = service.evaluate_strategies(
        assessment.id,
        RegimeStrategyEvaluationRequest(
            workspace_id="ws-1",
            actor_id="risk-engine",
            rules=[StrategyRegimeRule(strategy_id="ict-trend", allowed_regimes=[assessment.primary_regime])],
        ),
    )
    assert assessment.tradability == RegimeDecision.block
    assert result.evaluations[0].decision == RegimeDecision.block


def test_strategy_permissions_are_regime_specific() -> None:
    service = ExecutiveMarketRegimeService()
    assessment = service.assess(payload())
    result = service.evaluate_strategies(
        assessment.id,
        RegimeStrategyEvaluationRequest(
            workspace_id="ws-1",
            actor_id="orchestrator",
            rules=[
                StrategyRegimeRule(strategy_id="ict-trend", allowed_regimes=[MarketRegime.strong_trend]),
                StrategyRegimeRule(strategy_id="mean-reversion", blocked_regimes=[MarketRegime.strong_trend]),
                StrategyRegimeRule(strategy_id="delta-challenger", shadow_regimes=[MarketRegime.strong_trend]),
            ],
        ),
    )
    decisions = {item.strategy_id: item.decision for item in result.evaluations}
    assert decisions == {
        "ict-trend": RegimeDecision.allow,
        "mean-reversion": RegimeDecision.block,
        "delta-challenger": RegimeDecision.shadow_only,
    }


def test_workspace_and_account_profile_isolation() -> None:
    service = ExecutiveMarketRegimeService()
    first = service.assess(payload("ws-1", "ftmo"))
    service.assess(payload("ws-2", "e8"))
    assert service.get(first.id, "ws-2") is None
    assert len(service.list_assessments("ws-1", "ftmo")) == 1
    assert len(service.list_assessments("ws-1", "e8")) == 0


def test_news_risk_forces_no_trade() -> None:
    service = ExecutiveMarketRegimeService()
    request = payload()
    request.features.news_risk = 0.95
    assessment = service.assess(request)
    assert assessment.primary_regime == MarketRegime.news_driven
    assert assessment.tradability == RegimeDecision.block


def test_audit_trail_records_assessment_and_strategy_evaluation() -> None:
    service = ExecutiveMarketRegimeService()
    assessment = service.assess(payload())
    service.evaluate_strategies(
        assessment.id,
        RegimeStrategyEvaluationRequest(
            workspace_id="ws-1",
            actor_id="orchestrator",
            rules=[StrategyRegimeRule(strategy_id="ict", allowed_regimes=[MarketRegime.strong_trend])],
        ),
    )
    actions = [record.action for record in service.audit_records("ws-1")]
    assert actions == ["market_regime_assessed", "strategy_regime_evaluated"]
