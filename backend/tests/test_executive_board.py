import pytest
from pydantic import ValidationError

from app.executive_board.models import BoardPortfolioCreate, GovernanceIssueUpdate
from app.executive_board.service import ExecutiveBoardService


def payload(workspace_id: str = "ws-1", name: str = "Enterprise board") -> BoardPortfolioCreate:
    return BoardPortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="chair-1",
        members=[
            {
                "member_id": "director-1",
                "name": "Independent Director",
                "independent": True,
                "attendance_score": 95,
                "skill_coverage_score": 82,
                "challenge_effectiveness_score": 80,
                "succession_readiness_score": 60,
            },
            {
                "member_id": "director-2",
                "name": "Executive Director",
                "independent": False,
                "attendance_score": 88,
                "skill_coverage_score": 62,
                "challenge_effectiveness_score": 58,
                "succession_readiness_score": 55,
            },
        ],
        committees=[
            {
                "committee_id": "risk",
                "name": "Risk Committee",
                "committee_type": "risk",
                "member_ids": ["director-1", "director-2"],
                "charter_coverage_score": 80,
                "agenda_quality_score": 55,
                "information_quality_score": 60,
                "decision_cycle_days": 55,
                "action_closure_score": 58,
            }
        ],
        issues=[
            {
                "issue_id": "succession-gap",
                "title": "Chair succession gap",
                "severity": "critical",
                "probability": 0.8,
                "impact_score": 90,
                "committee_id": "risk",
                "remediation_progress": 20,
            }
        ],
    )


def test_assessment_detects_vulnerable_committees_and_priority_issues() -> None:
    service = ExecutiveBoardService()
    item = service.create(payload())
    assessed = service.assess(item.id, "ws-1", "chair-1")
    assert assessed.assessment is not None
    assert "risk" in assessed.assessment.vulnerable_committees
    assert "succession-gap" in assessed.assessment.priority_issues
    assert assessed.assessment.issue_exposure_score > 0


def test_issue_update_and_workspace_isolation() -> None:
    service = ExecutiveBoardService()
    item = service.create(payload())
    updated = service.update_issue(
        item.id,
        "ws-1",
        GovernanceIssueUpdate(issue_id="succession-gap", remediation_progress=85, actor_id="chair-2"),
    )
    assert updated.issues[0].remediation_progress == 85
    assert service.get(item.id, "other-workspace") is None
    assert len(service.audit_records("ws-1")) == 2


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveBoardService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_member_reference_is_rejected() -> None:
    data = payload().model_dump()
    data["committees"][0]["member_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        BoardPortfolioCreate(**data)
