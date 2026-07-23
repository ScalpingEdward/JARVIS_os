import pytest

from app.schemas.real_time_portfolio_ai_brain import (
    IntelligenceSignal,
    PortfolioBrainAction,
    PortfolioBrainCreate,
    PortfolioBrainState,
)
from app.services.real_time_portfolio_ai_brain import (
    PortfolioBrainError,
    RealTimePortfolioAIBrainService,
)


def payload(source_key: str = "snapshot-1", blocked: bool = False) -> PortfolioBrainCreate:
    return PortfolioBrainCreate(
        workspace_id="workspace-a",
        source_key=source_key,
        signals=[
            IntelligenceSignal(domain="macro", signal_key="macro-1", direction=0.6, severity=0.3, confidence=0.9, freshness=0.9),
            IntelligenceSignal(domain="infrastructure", signal_key="infra-1", direction=0.2, severity=0.2, confidence=0.9, freshness=1.0, risk_blocked=blocked),
        ],
        current_gross_exposure=0.7,
        current_net_exposure=0.4,
        current_drawdown=0.05,
        liquidity_buffer=0.8,
        requested_by="analyst",
    )


def test_scores_and_recommendations_are_created() -> None:
    service = RealTimePortfolioAIBrainService()
    record = service.create(payload())
    assert record.state == PortfolioBrainState.SCORED
    assert 0 <= record.scores.decision_confidence <= 1
    assert record.recommendations


def test_duplicate_source_key_is_rejected_per_workspace() -> None:
    service = RealTimePortfolioAIBrainService()
    service.create(payload())
    with pytest.raises(PortfolioBrainError, match="duplicate source key"):
        service.create(payload())


def test_workspace_isolation() -> None:
    service = RealTimePortfolioAIBrainService()
    record = service.create(payload())
    with pytest.raises(PortfolioBrainError, match="record not found"):
        service.get("workspace-b", record.record_id)


def test_human_approval_required_before_activation() -> None:
    service = RealTimePortfolioAIBrainService()
    record = service.create(payload())
    with pytest.raises(PortfolioBrainError, match="human approval required"):
        service.act("workspace-a", record.record_id, PortfolioBrainAction(action="activate", actor="operator", operation_id="op-1"))
    approved = service.act("workspace-a", record.record_id, PortfolioBrainAction(action="approve", actor="risk-officer", operation_id="op-2"))
    active = service.act("workspace-a", record.record_id, PortfolioBrainAction(action="activate", actor="operator", operation_id="op-3"))
    assert approved.approved_by == "risk-officer"
    assert active.state == PortfolioBrainState.ACTIVE


def test_operation_replay_is_rejected() -> None:
    service = RealTimePortfolioAIBrainService()
    record = service.create(payload())
    command = PortfolioBrainAction(action="submit-review", actor="analyst", operation_id="same-operation")
    service.act("workspace-a", record.record_id, command)
    with pytest.raises(PortfolioBrainError, match="operation replay detected"):
        service.act("workspace-a", record.record_id, command)


def test_risk_brain_hard_block_is_authoritative() -> None:
    service = RealTimePortfolioAIBrainService()
    record = service.create(payload(blocked=True))
    assert record.state == PortfolioBrainState.BLOCKED
    assert "risk-brain-hard-block" in record.risk_flags
    with pytest.raises(PortfolioBrainError, match="hard block"):
        service.act("workspace-a", record.record_id, PortfolioBrainAction(action="approve", actor="risk-officer", operation_id="blocked-op"))


def test_safety_boundary_status_contract() -> None:
    from app.api.routes.real_time_portfolio_ai_brain import status_view

    status = status_view()
    assert status["portfolio_mutation_enabled"] is False
    assert status["allocation_mutation_enabled"] is False
    assert status["routing_mutation_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["human_approval_required"] is True
