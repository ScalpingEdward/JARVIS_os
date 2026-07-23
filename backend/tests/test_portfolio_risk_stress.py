import pytest

from app.schemas.portfolio_risk_stress import (
    PortfolioRiskAction,
    PortfolioRiskRecordCreate,
    PortfolioRiskState,
)
from app.services.portfolio_risk_stress import PortfolioRiskStressService


@pytest.fixture
def service() -> PortfolioRiskStressService:
    return PortfolioRiskStressService()


def payload(workspace: str = "ws-a", source_key: str = "portfolio-1") -> PortfolioRiskRecordCreate:
    return PortfolioRiskRecordCreate(
        workspace_id=workspace,
        source_key=source_key,
        requested_by="risk-analyst",
        observations=[
            {
                "sleeve": "macro",
                "asset_class": "commodities",
                "market_value": 500000,
                "weight": 0.5,
                "volatility": 0.18,
                "beta": 0.7,
                "liquidity_days": 2,
                "expected_shortfall_pct": 4.5,
                "stress_loss_pct": 9,
                "drawdown_pct": 8,
                "correlation_cluster": "inflation-assets",
                "confidence": 0.95,
                "freshness": 0.98,
                "provenance": ["risk-engine", "custodian"],
            },
            {
                "sleeve": "rates",
                "asset_class": "fixed-income",
                "market_value": 500000,
                "weight": 0.5,
                "volatility": 0.08,
                "beta": 0.25,
                "liquidity_days": 1,
                "expected_shortfall_pct": 2.5,
                "stress_loss_pct": 5,
                "drawdown_pct": 4,
                "correlation_cluster": "duration-assets",
                "confidence": 0.92,
                "freshness": 0.97,
                "provenance": ["risk-engine", "benchmark"],
            },
        ],
    )


def test_scores_portfolio_risk_record(service: PortfolioRiskStressService) -> None:
    record = service.create(payload())
    assert record.state in {PortfolioRiskState.SCORED, PortfolioRiskState.REVIEW_REQUIRED}
    assert 0 <= record.scores.risk_resilience <= 100
    assert record.scores.stress_loss_pct > 0


def test_duplicate_source_key_is_rejected_per_workspace(service: PortfolioRiskStressService) -> None:
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.create(payload("ws-b")).workspace_id == "ws-b"


def test_workspace_isolation(service: PortfolioRiskStressService) -> None:
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")


def test_human_approval_and_replay_protection(service: PortfolioRiskStressService) -> None:
    record = service.create(payload())
    action = PortfolioRiskAction(action="approve", actor="risk-officer", operation_id="op-1")
    approved = service.act(record.record_id, "ws-a", action)
    replayed = service.act(record.record_id, "ws-a", action)
    assert approved.state == PortfolioRiskState.APPROVED
    assert approved.approved_by == "risk-officer"
    assert replayed.version == approved.version


def test_risk_brain_hard_block_is_authoritative(service: PortfolioRiskStressService) -> None:
    record = service.create(payload())
    blocked = service.act(
        record.record_id,
        "ws-a",
        PortfolioRiskAction(action="activate", actor="operator", operation_id="op-block"),
        risk_blocked=True,
    )
    assert blocked.state == PortfolioRiskState.BLOCKED
    assert "risk-brain-hard-block" in blocked.risk_flags


def test_module_never_mutates_allocations_or_executes(service: PortfolioRiskStressService) -> None:
    status = service.status()
    assert status["allocation_mutation_enabled"] is False
    assert status["execution_enabled"] is False
