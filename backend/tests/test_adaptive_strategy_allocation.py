import pytest

from app.schemas.adaptive_strategy_allocation import (
    StrategyAllocationAction,
    StrategyAllocationCreate,
    StrategyAllocationState,
)
from app.services.adaptive_strategy_allocation import AdaptiveStrategyAllocationService


@pytest.fixture
def service() -> AdaptiveStrategyAllocationService:
    return AdaptiveStrategyAllocationService()


def payload(workspace: str = "ws-a", source_key: str = "allocation-1") -> StrategyAllocationCreate:
    return StrategyAllocationCreate(
        workspace_id=workspace,
        source_key=source_key,
        requested_by="portfolio-analyst",
        max_strategy_weight=0.65,
        max_turnover=0.50,
        observations=[
            {
                "strategy_id": "xau-trend",
                "regime": "trend",
                "expected_return": 0.12,
                "realized_return": 0.10,
                "volatility": 0.08,
                "downside_deviation": 0.04,
                "max_drawdown": 0.08,
                "win_rate": 0.58,
                "profit_factor": 1.75,
                "alpha_persistence": 0.82,
                "regime_fit": 0.90,
                "average_correlation": 0.30,
                "liquidity_score": 0.95,
                "turnover_rate": 0.15,
                "current_weight": 0.50,
                "confidence": 0.94,
                "freshness": 0.98,
                "provenance": ["strategy-ledger", "risk-engine"],
            },
            {
                "strategy_id": "fx-mean-reversion",
                "regime": "range",
                "expected_return": 0.07,
                "realized_return": 0.05,
                "volatility": 0.07,
                "downside_deviation": 0.04,
                "max_drawdown": 0.10,
                "win_rate": 0.61,
                "profit_factor": 1.45,
                "alpha_persistence": 0.70,
                "regime_fit": 0.72,
                "average_correlation": 0.25,
                "liquidity_score": 0.92,
                "turnover_rate": 0.18,
                "current_weight": 0.50,
                "confidence": 0.91,
                "freshness": 0.96,
                "provenance": ["strategy-ledger", "risk-engine"],
            },
        ],
    )


def test_scores_and_normalizes_strategy_recommendations(service: AdaptiveStrategyAllocationService) -> None:
    record = service.create(payload())
    assert record.state in {StrategyAllocationState.SCORED, StrategyAllocationState.REVIEW_REQUIRED}
    assert round(sum(item.recommended_weight for item in record.recommendations), 5) == 1
    assert all(0 <= item.health_score <= 100 for item in record.recommendations)


def test_duplicate_source_key_is_rejected_per_workspace(service: AdaptiveStrategyAllocationService) -> None:
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.create(payload("ws-b")).workspace_id == "ws-b"


def test_workspace_isolation(service: AdaptiveStrategyAllocationService) -> None:
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")


def test_human_approval_and_replay_protection(service: AdaptiveStrategyAllocationService) -> None:
    record = service.create(payload())
    action = StrategyAllocationAction(action="approve", actor="risk-officer", operation_id="op-1")
    approved = service.act(record.record_id, "ws-a", action)
    version = approved.version
    replayed = service.act(record.record_id, "ws-a", action)
    assert approved.state == StrategyAllocationState.APPROVED
    assert approved.approved_by == "risk-officer"
    assert replayed.version == version


def test_risk_brain_hard_block_is_authoritative(service: AdaptiveStrategyAllocationService) -> None:
    record = service.create(payload())
    blocked = service.act(
        record.record_id,
        "ws-a",
        StrategyAllocationAction(action="activate", actor="operator", operation_id="op-block"),
        risk_blocked=True,
    )
    assert blocked.state == StrategyAllocationState.BLOCKED
    assert "risk-brain-hard-block" in blocked.risk_flags


def test_module_never_mutates_allocations_or_activates_strategies(
    service: AdaptiveStrategyAllocationService,
) -> None:
    status = service.status()
    assert status["allocation_mutation_enabled"] is False
    assert status["strategy_activation_enabled"] is False
    assert status["execution_enabled"] is False
