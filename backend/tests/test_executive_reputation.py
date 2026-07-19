import pytest
from pydantic import ValidationError

from app.executive_reputation.models import ReputationIssueUpdate, ReputationPortfolioCreate
from app.executive_reputation.service import ExecutiveReputationService


def payload(workspace_id: str = "ws-1", name: str = "Enterprise reputation") -> ReputationPortfolioCreate:
    return ReputationPortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="exec-1",
        stakeholder_segments=[
            {
                "segment_id": "investors",
                "name": "Investors",
                "stakeholder_type": "investor",
                "influence_score": 95,
                "trust_score": 52,
                "sentiment_score": -20,
                "engagement_score": 60,
                "narrative_alignment_score": 48,
                "media_exposure_score": 80,
            },
            {
                "segment_id": "customers",
                "name": "Customers",
                "stakeholder_type": "customer",
                "influence_score": 90,
                "trust_score": 78,
                "sentiment_score": 25,
                "engagement_score": 82,
                "narrative_alignment_score": 76,
                "media_exposure_score": 65,
            },
        ],
        issues=[
            {
                "issue_id": "service-outage",
                "title": "Service outage narrative",
                "severity": "critical",
                "probability": 0.8,
                "velocity_score": 90,
                "stakeholder_segment_ids": ["investors", "customers"],
                "remediation_progress": 20,
                "response_readiness_score": 45,
            }
        ],
        channels=[
            {
                "channel_id": "press",
                "name": "Press office",
                "reach_score": 85,
                "credibility_score": 75,
                "response_speed_score": 55,
                "monitoring_coverage_score": 60,
            }
        ],
    )


def test_assessment_detects_vulnerable_segments_and_priority_issues() -> None:
    service = ExecutiveReputationService()
    item = service.create(payload())
    assessed = service.assess(item.id, "ws-1", "exec-1")
    assert assessed.assessment is not None
    assert "investors" in assessed.assessment.vulnerable_segments
    assert "service-outage" in assessed.assessment.priority_issues
    assert assessed.assessment.issue_exposure_score > 0


def test_issue_update_and_workspace_isolation() -> None:
    service = ExecutiveReputationService()
    item = service.create(payload())
    updated = service.update_issue(
        item.id,
        "ws-1",
        ReputationIssueUpdate(issue_id="service-outage", remediation_progress=85, response_readiness_score=80, actor_id="exec-2"),
    )
    assert updated.issues[0].remediation_progress == 85
    assert service.get(item.id, "other-workspace") is None
    assert len(service.audit_records("ws-1")) == 2


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveReputationService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_stakeholder_reference_is_rejected() -> None:
    data = payload().model_dump()
    data["issues"][0]["stakeholder_segment_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        ReputationPortfolioCreate(**data)
