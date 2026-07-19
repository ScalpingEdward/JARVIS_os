import pytest

from app.executive_risk_brain.models import RiskBrainRunCreate, RiskState
from app.executive_risk_brain.service import ExecutiveRiskBrainService


def payload(**overrides):
    data = {
        "workspace_id": "ws-a",
        "account_profile_id": "funded-100k",
        "actor_id": "risk-officer",
        "source_reference": "risk-001",
        "components": {
            "portfolio_heat": 35,
            "drawdown_risk": 30,
            "correlation_risk": 25,
            "concentration_risk": 20,
            "liquidity_risk": 15,
            "volatility_risk": 30,
            "news_risk": 10,
            "tail_risk": 20,
            "model_risk": 15,
            "operational_risk": 10,
            "confidence_risk": 20,
        },
        "strategies": [
            {
                "strategy_id": "ict-trend",
                "symbol": "XAUUSD",
                "asset_cluster": "metals",
                "current_weight": 0.3,
                "risk_contribution": 20,
                "adaptive_score": 84,
                "confidence": 78,
                "drawdown_pct": 8,
                "correlation_to_portfolio": 0.35,
            }
        ],
    }
    data.update(overrides)
    return RiskBrainRunCreate(**data)


def test_low_risk_run_is_normal():
    service = ExecutiveRiskBrainService()
    run = service.create(payload())
    assert run.global_state == RiskState.normal
    assert run.strategy_decisions[0].state == RiskState.normal
    assert run.autonomous_execution_enabled is False


def test_heat_and_drawdown_hard_block_portfolio():
    service = ExecutiveRiskBrainService()
    item = payload(
        source_reference="risk-block",
        components={
            "portfolio_heat": 85,
            "drawdown_risk": 85,
            "correlation_risk": 80,
            "concentration_risk": 75,
            "liquidity_risk": 65,
            "volatility_risk": 80,
            "news_risk": 60,
            "tail_risk": 85,
            "model_risk": 50,
            "operational_risk": 35,
            "confidence_risk": 70,
        },
    )
    run = service.create(item)
    assert run.global_state == RiskState.blocked
    assert all(decision.state == RiskState.blocked for decision in run.strategy_decisions)


def test_high_news_risk_freezes_new_exposure():
    service = ExecutiveRiskBrainService()
    item = payload(source_reference="risk-news")
    item.components.news_risk = 90
    run = service.create(item)
    assert run.global_state == RiskState.frozen
    assert run.strategy_decisions[0].recommended_weight_multiplier == 0.0


def test_risk_velocity_detects_acceleration():
    service = ExecutiveRiskBrainService()
    item = payload(source_reference="risk-velocity", previous_global_risk_score=5)
    run = service.create(item)
    assert run.metrics.risk_velocity > 12
    assert run.metrics.risk_trend.value == "accelerating"
    assert run.metrics.forecast_risk_score >= run.metrics.global_risk_score


def test_workspace_isolation_and_audit():
    service = ExecutiveRiskBrainService()
    created = service.create(payload())
    assert service.get(created.id, "ws-b") is None
    assert service.list_runs("ws-b") == []
    assert len(service.audit_records("ws-a")) == 1
    assert service.audit_records("ws-b") == []


def test_duplicate_source_reference_rejected():
    service = ExecutiveRiskBrainService()
    service.create(payload())
    with pytest.raises(ValueError, match="Duplicate"):
        service.create(payload())


def test_invalid_threshold_order_rejected():
    with pytest.raises(ValueError, match="strictly increasing"):
        payload(thresholds={"reduced_score": 70, "frozen_score": 60, "blocked_score": 80})
