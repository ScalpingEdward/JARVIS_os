from uuid import uuid4

import pytest

from app.executive_order_flow.models import (
    DataQuality,
    MicrostructureRisk,
    OrderFlowPortfolioCreate,
    OrderFlowRiskUpdate,
    OrderFlowSnapshot,
    PriceLevel,
)
from app.executive_order_flow.service import ExecutiveOrderFlowService


def payload(workspace_id: str = "alpha") -> OrderFlowPortfolioCreate:
    return OrderFlowPortfolioCreate(
        workspace_id=workspace_id,
        name="XAU futures order flow",
        snapshots=[
            OrderFlowSnapshot(
                symbol="GC",
                venue="CME",
                data_quality=DataQuality.exchange,
                best_bid=2400.0,
                best_ask=2400.1,
                levels=[
                    PriceLevel(price=2400.0, bid_volume=30, ask_volume=130),
                    PriceLevel(price=2400.1, bid_volume=25, ask_volume=110),
                    PriceLevel(price=2399.9, bid_volume=80, ask_volume=75),
                ],
            )
        ],
        risks=[MicrostructureRisk(name="news volatility", severity=30, probability=40)],
    )


def test_assessment_produces_bias_and_preserves_execution_gate() -> None:
    service = ExecutiveOrderFlowService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "alpha", "trader")
    assert assessed.assessment is not None
    assert assessed.assessment.cumulative_delta > 0
    assert assessed.assessment.data_reliability_score == 100
    assert assessed.assessment.directional_bias.value == "buy"
    assert assessed.autonomous_execution_enabled is False


def test_low_quality_data_forces_no_trade() -> None:
    service = ExecutiveOrderFlowService()
    item_payload = payload()
    item_payload.snapshots[0].data_quality = DataQuality.broker_tick
    item = service.create(item_payload)
    assessed = service.assess(item.portfolio_id, "alpha", "trader")
    assert assessed.assessment is not None
    assert assessed.assessment.no_trade is True
    assert any("data quality" in reason.lower() for reason in assessed.assessment.reasons)


def test_workspace_isolation_and_duplicate_guard() -> None:
    service = ExecutiveOrderFlowService()
    item = service.create(payload("alpha"))
    assert service.get(item.portfolio_id, "beta") is None
    with pytest.raises(ValueError):
        service.create(payload("alpha"))
    assert service.create(payload("beta")).workspace_id == "beta"


def test_risk_update_is_governed_and_audited() -> None:
    service = ExecutiveOrderFlowService()
    item = service.create(payload())
    risk_id = item.risks[0].risk_id
    updated = service.update_risk(
        item.portfolio_id,
        "alpha",
        OrderFlowRiskUpdate(risk_id=risk_id, severity=70, actor_id="risk-manager"),
    )
    assert updated.risks[0].severity == 70
    assert any(record.action == "risk.updated" for record in service.audit_records("alpha"))


def test_invalid_crossed_book_is_rejected() -> None:
    with pytest.raises(ValueError):
        OrderFlowSnapshot(
            symbol="GC",
            venue="CME",
            data_quality=DataQuality.exchange,
            best_bid=2401,
            best_ask=2400,
            levels=[PriceLevel(price=2400, bid_volume=1, ask_volume=1)],
        )


def test_missing_risk_raises_key_error() -> None:
    service = ExecutiveOrderFlowService()
    item = service.create(payload())
    with pytest.raises(KeyError):
        service.update_risk(item.portfolio_id, "alpha", OrderFlowRiskUpdate(risk_id=uuid4(), severity=1, actor_id="x"))
