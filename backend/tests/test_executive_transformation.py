import pytest

from app.executive_transformation.models import (
    ChangeReadiness,
    ProgressUpdate,
    TransformationBenefit,
    TransformationPortfolioCreate,
    TransformationProgram,
)
from app.executive_transformation.service import ExecutiveTransformationService


def payload(workspace_id: str = "ws-a") -> TransformationPortfolioCreate:
    readiness = ChangeReadiness(stakeholder_alignment=80, capability_readiness=75, adoption_readiness=70, communication_readiness=85)
    return TransformationPortfolioCreate(
        workspace_id=workspace_id,
        owner_id="owner",
        title="Enterprise transformation",
        portfolio_budget=1000,
        programs=[
            TransformationProgram(program_key="foundation", title="Foundation", owner_id="a", strategic_value=90, progress=100, budget=400, spent=350, risk_score=20, benefits=[TransformationBenefit(key="b1", title="Foundation benefit", target_value=100, realized_value=80, weight=100)], readiness=readiness),
            TransformationProgram(program_key="scale", title="Scale", owner_id="b", strategic_value=85, progress=50, budget=500, spent=250, risk_score=35, dependencies=["foundation"], benefits=[TransformationBenefit(key="b2", title="Scale benefit", target_value=200, realized_value=60, weight=100)], readiness=readiness),
        ],
    )


def test_assessment_builds_health_benefits_and_critical_path() -> None:
    service = ExecutiveTransformationService()
    record = service.create(payload())
    assessed = service.assess(record.id, "ws-a", "analyst")
    assert assessed.assessment is not None
    assert assessed.assessment.critical_path == ["foundation", "scale"]
    assert assessed.assessment.portfolio_health > 0
    assert assessed.assessment.autonomous_actions_enabled is False


def test_progress_update_invalidates_assessment_and_tracks_benefits() -> None:
    service = ExecutiveTransformationService()
    record = service.create(payload())
    service.assess(record.id, "ws-a", "analyst")
    updated = service.update_progress(record.id, "ws-a", ProgressUpdate(actor_id="operator", program_key="scale", progress=80, spent=300, risk_score=20, realized_benefits={"b2": 120}))
    assert updated.assessment is None
    assert updated.programs[1].benefits[0].realized_value == 120


def test_workspace_isolation_duplicates_status_and_audit() -> None:
    service = ExecutiveTransformationService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    with pytest.raises(ValueError):
        service.create(payload())
    service.assess(record.id, "ws-a", "analyst")
    status = service.status("ws-a")
    assert status.version == "18.6"
    assert status.portfolios == 1
    assert status.assessed_portfolios == 1
    assert len(service.audit_records("ws-a")) == 2
    assert service.audit_records("ws-b") == []


def test_cycles_and_unknown_dependencies_are_rejected() -> None:
    data = payload()
    data.programs[0].dependencies = ["scale"]
    service = ExecutiveTransformationService()
    record = service.create(data)
    with pytest.raises(ValueError):
        service.assess(record.id, "ws-a", "analyst")

    with pytest.raises(ValueError):
        TransformationPortfolioCreate(
            workspace_id="ws",
            owner_id="owner",
            title="Invalid",
            portfolio_budget=10,
            programs=[TransformationProgram(program_key="x", title="X", owner_id="x", strategic_value=50, dependencies=["missing"], readiness=ChangeReadiness(stakeholder_alignment=50, capability_readiness=50, adoption_readiness=50, communication_readiness=50))],
        )
