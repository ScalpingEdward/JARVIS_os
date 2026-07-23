import pytest

from backend.app.phoenix.v21_59_multi_regime_portfolio_rotation.models import (
    RegimeSleeve,
    RotationAction,
    RotationCreate,
    RotationState,
)
from backend.app.phoenix.v21_59_multi_regime_portfolio_rotation.service import (
    GovernanceError,
    PortfolioRotationGovernanceService,
)


def sleeve(
    sleeve_id: str,
    current: float,
    proposed: float,
    bucket: str,
    fit: float = 85,
    liquidity: float = 85,
    confidence: float = 0.85,
    drawdown: float = 4,
) -> RegimeSleeve:
    return RegimeSleeve(
        sleeve_id=sleeve_id,
        strategy_id=f"strategy-{sleeve_id}",
        target_regime="stable-trend",
        current_weight_pct=current,
        proposed_weight_pct=proposed,
        expected_alpha_pct=6,
        drawdown_pct=drawdown,
        liquidity_score=liquidity,
        regime_fit_score=fit,
        confidence=confidence,
        correlation_bucket=bucket,
        capacity_limit=600_000,
        proposed_capital=proposed * 10_000,
    )


def payload(workspace: str = "ws-a", source: str = "rotation-1") -> RotationCreate:
    return RotationCreate(
        workspace_id=workspace,
        source_key=source,
        portfolio_id="portfolio-1",
        active_regime="stable-trend",
        total_capital=1_000_000,
        sleeves=[
            sleeve("trend", 50, 35, "trend"),
            sleeve("range", 25, 30, "range"),
            sleeve("defensive", 25, 35, "defensive"),
        ],
        evidence_refs=["regime:v21.58:validated"],
    )


def advance_to_rotation(service: PortfolioRotationGovernanceService, record_id: str) -> None:
    actions = [
        "prepare-evidence",
        "analyze",
        "prepare-rotation",
        "request-review",
    ]
    for action in actions:
        service.act(record_id, "ws-a", RotationAction(action=action, actor="tester"))
    service.act(
        record_id,
        "ws-a",
        RotationAction(action="approve", actor="human", approval_token="approval-1"),
    )
    service.act(
        record_id,
        "ws-a",
        RotationAction(action="start-rotation", actor="runtime", operation_receipt="rotation-1"),
    )


def test_full_rotation_lifecycle_reaches_verified() -> None:
    service = PortfolioRotationGovernanceService()
    record = service.create(payload())
    advance_to_rotation(service, record.record_id)
    assert service.get(record.record_id, "ws-a").state == RotationState.ROTATING
    for _ in range(3):
        service.act(record.record_id, "ws-a", RotationAction(action="observe", actor="monitor"))
    assert service.get(record.record_id, "ws-a").state == RotationState.VERIFIED
    assert service.get(record.record_id, "ws-a").violations == []


def test_constraint_violation_escalates() -> None:
    service = PortfolioRotationGovernanceService()
    record = service.create(payload())
    advance_to_rotation(service, record.record_id)
    unhealthy = [
        sleeve("trend", 50, 60, "trend", fit=40),
        sleeve("range", 25, 20, "trend"),
        sleeve("defensive", 25, 20, "defensive"),
    ]
    result = service.act(
        record.record_id,
        "ws-a",
        RotationAction(action="observe", actor="monitor", sleeves=unhealthy),
    )
    assert result.state == RotationState.ESCALATED
    assert result.violations


def test_approval_and_operation_replay_protection() -> None:
    service = PortfolioRotationGovernanceService()
    first = service.create(payload())
    advance_to_rotation(service, first.record_id)
    second = service.create(payload(source="rotation-2"))
    for action in ["prepare-evidence", "analyze", "prepare-rotation", "request-review"]:
        service.act(second.record_id, "ws-a", RotationAction(action=action, actor="tester"))
    with pytest.raises(GovernanceError, match="approval_token replay"):
        service.act(
            second.record_id,
            "ws-a",
            RotationAction(action="approve", actor="human", approval_token="approval-1"),
        )


def test_risk_brain_block_is_authoritative() -> None:
    service = PortfolioRotationGovernanceService()
    blocked = payload(source="blocked").model_copy(update={"risk_brain_blocked": True})
    record = service.create(blocked)
    assert record.state == RotationState.BLOCKED
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(record.record_id, "ws-a", RotationAction(action="prepare-evidence", actor="tester"))


def test_duplicate_source_and_workspace_isolation() -> None:
    service = PortfolioRotationGovernanceService()
    record = service.create(payload())
    with pytest.raises(GovernanceError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "ws-b")
    assert service.list("ws-b") == []
