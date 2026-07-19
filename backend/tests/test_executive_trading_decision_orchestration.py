import pytest

from app.executive_decision_engine.trading_models import (
    PortfolioState,
    RiskState,
    StrategyDecisionInput,
    TradingDecision,
    TradingDecisionCreate,
)
from app.executive_decision_engine.trading_service import TradingDecisionOrchestrationService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        owner_id="owner-1",
        source_key="decision-1",
        account_profile="ftmo-100k",
        symbol="XAUUSD",
        timeframe="M15",
        regime_confidence=82,
        evidence_score=78,
        portfolio_score=80,
        portfolio_state=PortfolioState.strong,
        global_risk_score=24,
        risk_state=RiskState.normal,
        news_risk=20,
        strategies=[StrategyDecisionInput(strategy_key="ict-trend", adaptive_score=88, confidence=84, portfolio_weight=35, risk_weight_multiplier=1)],
    )
    data.update(overrides)
    return TradingDecisionCreate(**data)


def test_approves_best_strategy_when_all_gates_pass():
    service = TradingDecisionOrchestrationService()
    result = service.create(payload())
    assert result.decision == TradingDecision.approve
    assert result.selected_strategy_key == "ict-trend"
    assert result.recommended_weight == 35
    assert result.autonomous_actions_enabled is False
    assert len(result.decision_hash) == 64


def test_blocked_risk_rejects_and_removes_strategy():
    service = TradingDecisionOrchestrationService()
    result = service.create(payload(source_key="blocked", risk_state=RiskState.blocked, global_risk_score=92))
    assert result.decision == TradingDecision.reject
    assert result.selected_strategy_key is None
    assert result.recommended_weight == 0


def test_reduced_risk_halves_risk_adjusted_weight():
    service = TradingDecisionOrchestrationService()
    result = service.create(payload(source_key="reduced", risk_state=RiskState.reduced, global_risk_score=55))
    assert result.decision == TradingDecision.reduce
    assert result.recommended_weight == 17.5


def test_shadow_only_strategy_cannot_be_approved():
    service = TradingDecisionOrchestrationService()
    strategy = StrategyDecisionInput(strategy_key="challenger", adaptive_score=90, confidence=70, portfolio_weight=25, risk_weight_multiplier=1, shadow_only=True)
    result = service.create(payload(source_key="shadow", strategies=[strategy]))
    assert result.decision == TradingDecision.shadow
    assert result.recommended_weight == 0


def test_workspace_isolation_and_duplicate_protection():
    service = TradingDecisionOrchestrationService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert service.list_records("other") == []
    with pytest.raises(ValueError):
        service.create(payload())
