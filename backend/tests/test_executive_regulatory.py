from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.executive_regulatory.models import ComplianceIssueUpdate, RegulatoryPortfolioCreate
from app.executive_regulatory.service import ExecutiveRegulatoryService


def payload(workspace_id: str = "ws-a") -> RegulatoryPortfolioCreate:
    return RegulatoryPortfolioCreate(
        workspace_id=workspace_id,
        name="EU Compliance 2026",
        executive_owner_id="chief-compliance",
        strategy_portfolio_id=uuid4(),
        obligations=[
            {
                "obligation_id": "eu-ai-act",
                "title": "EU AI Act readiness",
                "jurisdiction": "EU",
                "authority": "EU Commission",
                "owner_id": "ai-governance",
                "materiality": 1.0,
                "control_coverage": 0.55,
                "evidence_readiness": 0.5,
                "implementation_progress": 0.6,
                "days_to_deadline": 20,
                "status": "at_risk",
            }
        ],
        issues=[
            {
                "issue_id": "gap-1",
                "obligation_id": "eu-ai-act",
                "severity": 0.9,
                "remediation_progress": 0.2,
                "financial_exposure": 250000,
                "reputational_exposure": 0.8,
            }
        ],
    )


def test_assessment_and_issue_update() -> None:
    service = ExecutiveRegulatoryService()
    portfolio = service.create(payload())
    assessed = service.assess(portfolio.id, "ws-a", "ceo")
    assert assessed.assessment is not None
    assert assessed.assessment.obligations_at_risk == ["eu-ai-act"]
    assert assessed.assessment.priority_issues == ["gap-1"]
    updated = service.update_issue(portfolio.id, "ws-a", ComplianceIssueUpdate(issue_id="gap-1", remediation_progress=0.8, actor_id="cco"))
    assert updated.issues[0].remediation_progress == 0.8
    assert len(service.audit_records("ws-a")) == 3


def test_workspace_isolation_and_duplicate_name() -> None:
    service = ExecutiveRegulatoryService()
    portfolio = service.create(payload())
    assert service.get(portfolio.id, "ws-b") is None
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_issue_reference_rejected() -> None:
    data = payload().model_dump()
    data["issues"][0]["obligation_id"] = "missing"
    with pytest.raises(ValidationError):
        RegulatoryPortfolioCreate(**data)
