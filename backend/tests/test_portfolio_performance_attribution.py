import pytest

from app.schemas.portfolio_performance_attribution import (
    AttributionAction,
    AttributionRecordCreate,
    AttributionState,
)
from app.services.portfolio_performance_attribution import PortfolioAttributionService


@pytest.fixture
def service() -> PortfolioAttributionService:
    return PortfolioAttributionService()


def payload(workspace: str = "ws-a", source_key: str = "portfolio-1") -> AttributionRecordCreate:
    return AttributionRecordCreate(
        workspace_id=workspace,
        source_key=source_key,
        requested_by="portfolio-analyst",
        observations=[
            {
                "sleeve": "macro-gold",
                "asset_class": "commodities",
                "strategy": "trend-following",
                "portfolio_return": 0.024,
                "benchmark_return": 0.015,
                "weight": 0.6,
                "active_risk": 0.03,
                "drawdown": 0.04,
                "turnover": 0.2,
                "transaction_cost_bps": 1.2,
                "confidence": 0.95,
                "freshness": 0.98,
                "provenance": ["portfolio-ledger", "benchmark-feed"],
            },
            {
                "sleeve": "fx-carry",
                "asset_class": "fx",
                "strategy": "carry",
                "portfolio_return": 0.009,
                "benchmark_return": 0.007,
                "weight": 0.4,
                "active_risk": 0.02,
                "drawdown": 0.03,
                "turnover": 0.1,
                "transaction_cost_bps": 0.8,
                "confidence": 0.9,
                "freshness": 0.97,
                "provenance": ["portfolio-ledger"],
            },
        ],
    )


def test_scores_attribution_record(service: PortfolioAttributionService) -> None:
    record = service.create(payload())
    assert record.state in {AttributionState.SCORED, AttributionState.REVIEW_REQUIRED}
    assert record.scores.active_return > 0
    assert 0 <= record.scores.alpha_persistence <= 100


def test_duplicate_source_key_is_rejected_per_workspace(service: PortfolioAttributionService) -> None:
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.create(payload("ws-b")).workspace_id == "ws-b"


def test_workspace_isolation(service: PortfolioAttributionService) -> None:
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")


def test_human_approval_and_replay_protection(service: PortfolioAttributionService) -> None:
    record = service.create(payload())
    action = AttributionAction(action="approve", actor="risk-officer", operation_id="op-1")
    approved = service.act(record.record_id, "ws-a", action)
    replayed = service.act(record.record_id, "ws-a", action)
    assert approved.state == AttributionState.APPROVED
    assert replayed.version == approved.version
    assert approved.approved_by == "risk-officer"


def test_risk_brain_hard_block_is_authoritative(service: PortfolioAttributionService) -> None:
    record = service.create(payload())
    blocked = service.act(
        record.record_id,
        "ws-a",
        AttributionAction(action="activate", actor="operator", operation_id="op-block"),
        risk_blocked=True,
    )
    assert blocked.state == AttributionState.BLOCKED
    assert "risk-brain-hard-block" in blocked.risk_flags


def test_module_never_mutates_allocations(service: PortfolioAttributionService) -> None:
    assert service.status()["allocation_mutation_enabled"] is False
