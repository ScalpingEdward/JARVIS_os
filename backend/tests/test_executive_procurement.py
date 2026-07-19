import pytest
from pydantic import ValidationError

from app.executive_procurement.models import ProcurementPortfolioCreate, ThirdPartyIssueUpdate
from app.executive_procurement.service import ExecutiveProcurementService


def payload(workspace_id: str = "ws-1") -> ProcurementPortfolioCreate:
    return ProcurementPortfolioCreate(
        workspace_id=workspace_id,
        name="Strategic suppliers",
        executive_owner_id="exec-1",
        suppliers=[
            {
                "supplier_id": "cloud-1",
                "name": "Cloud Core",
                "category": "technology",
                "owner_id": "owner-1",
                "annual_spend": 900000,
                "criticality": "critical",
                "contract_coverage": 0.65,
                "sla_performance": 0.88,
                "compliance_score": 0.7,
                "cyber_risk": 0.72,
                "operational_risk": 0.58,
                "financial_risk": 0.25,
                "exit_readiness": 0.3,
                "substitutability": 0.25,
            },
            {
                "supplier_id": "ops-2",
                "name": "Operations Partner",
                "category": "operations",
                "owner_id": "owner-2",
                "annual_spend": 100000,
                "criticality": "high",
                "contract_coverage": 0.9,
                "sla_performance": 0.94,
                "compliance_score": 0.92,
                "cyber_risk": 0.2,
                "operational_risk": 0.25,
                "financial_risk": 0.2,
                "exit_readiness": 0.8,
                "substitutability": 0.75,
            },
        ],
        issues=[
            {
                "issue_id": "risk-1",
                "supplier_id": "cloud-1",
                "title": "Untested exit plan",
                "risk_level": "severe",
                "probability": 0.7,
                "remediation_progress": 0.2,
                "owner_id": "owner-1",
            }
        ],
    )


def test_assessment_detects_concentration_and_vulnerability() -> None:
    service = ExecutiveProcurementService()
    created = service.create(payload())
    assessed = service.assess(created.id, "ws-1", "exec-1")
    assert assessed.assessment is not None
    assert assessed.assessment.concentration_exposure_score == 90
    assert "cloud-1" in assessed.assessment.vulnerable_suppliers
    assert "risk-1" in assessed.assessment.priority_issues
    assert assessed.assessment.executive_actions


def test_issue_update_and_workspace_isolation() -> None:
    service = ExecutiveProcurementService()
    created = service.create(payload())
    updated = service.update_issue(created.id, "ws-1", ThirdPartyIssueUpdate(issue_id="risk-1", remediation_progress=0.8, actor_id="risk-owner"))
    assert updated.issues[0].remediation_progress == 0.8
    assert service.get(created.id, "ws-2") is None
    assert service.audit_records("ws-1")


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveProcurementService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_supplier_reference_is_rejected() -> None:
    data = payload().model_dump()
    data["issues"][0]["supplier_id"] = "missing"
    with pytest.raises(ValidationError):
        ProcurementPortfolioCreate(**data)
