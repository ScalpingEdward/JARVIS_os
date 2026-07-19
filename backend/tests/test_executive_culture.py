from uuid import uuid4

import pytest

from app.executive_culture.models import CultureIssueUpdate, CulturePortfolioCreate
from app.executive_culture.service import ExecutiveCultureService


def payload(workspace_id: str = "workspace-a", name: str = "Culture Portfolio") -> CulturePortfolioCreate:
    return CulturePortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="ceo-1",
        workforce_portfolio_id=uuid4(),
        segments=[
            {
                "segment_id": "engineering",
                "name": "Engineering",
                "population": 120,
                "leadership_alignment": 72,
                "psychological_safety": 48,
                "collaboration_score": 70,
                "accountability_score": 68,
                "change_fatigue": 76,
                "trust_score": 52,
            },
            {
                "segment_id": "sales",
                "name": "Sales",
                "population": 80,
                "leadership_alignment": 81,
                "psychological_safety": 74,
                "collaboration_score": 78,
                "accountability_score": 82,
                "change_fatigue": 44,
                "trust_score": 79,
            },
        ],
        initiatives=[
            {
                "initiative_id": "operating-model",
                "name": "Operating Model Shift",
                "owner_id": "coo-1",
                "state": "adopting",
                "affected_segment_ids": ["engineering", "sales"],
                "strategic_importance": 95,
                "sponsor_commitment": 72,
                "communication_reach": 49,
                "manager_enablement": 51,
                "adoption_progress": 42,
                "resistance_level": 68,
            }
        ],
        issues=[
            {
                "issue_id": "change-fatigue",
                "title": "Concentrated change fatigue",
                "risk": "critical",
                "affected_segment_ids": ["engineering"],
                "probability": 0.8,
                "remediation_progress": 20,
            }
        ],
    )


def test_assessment_detects_vulnerabilities_and_actions() -> None:
    service = ExecutiveCultureService()
    item = service.create(payload())
    assessed = service.assess(item.id, "workspace-a", "ceo-1")
    assert assessed.assessment is not None
    assert "engineering" in assessed.assessment.vulnerable_segments
    assert "operating-model" in assessed.assessment.at_risk_initiatives
    assert "change-fatigue" in assessed.assessment.priority_issues
    assert assessed.assessment.executive_actions


def test_issue_update_and_workspace_isolation() -> None:
    service = ExecutiveCultureService()
    item = service.create(payload())
    updated = service.update_issue(item.id, "workspace-a", CultureIssueUpdate(issue_id="change-fatigue", remediation_progress=65, actor_id="chief-people-officer"))
    assert updated.issues[0].remediation_progress == 65
    assert service.get(item.id, "workspace-b") is None
    assert service.audit_records("workspace-a")


def test_duplicate_portfolio_rejected() -> None:
    service = ExecutiveCultureService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_segment_reference_rejected() -> None:
    data = payload().model_dump()
    data["initiatives"][0]["affected_segment_ids"] = ["unknown"]
    with pytest.raises(ValueError):
        CulturePortfolioCreate(**data)
