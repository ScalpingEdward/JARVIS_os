import pytest
from pydantic import ValidationError

from app.executive_geopolitical.models import GeopoliticalEventUpdate, GeopoliticalPortfolioCreate
from app.executive_geopolitical.service import ExecutiveGeopoliticalService


def payload(workspace_id: str = "ws-1", name: str = "Global country risk") -> GeopoliticalPortfolioCreate:
    return GeopoliticalPortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="exec-1",
        exposures=[
            {
                "exposure_id": "supplier-cn",
                "country_code": "CN",
                "country_name": "China",
                "exposure_type": "supplier",
                "annual_value": 12_000_000,
                "strategic_criticality": 92,
                "political_stability_score": 58,
                "sanctions_exposure_score": 62,
                "fx_transfer_risk_score": 55,
                "supply_dependency_score": 88,
                "continuity_readiness_score": 42,
                "substitutability_score": 35,
            },
            {
                "exposure_id": "revenue-de",
                "country_code": "DE",
                "country_name": "Germany",
                "exposure_type": "revenue",
                "annual_value": 8_000_000,
                "strategic_criticality": 75,
                "political_stability_score": 82,
                "sanctions_exposure_score": 15,
                "fx_transfer_risk_score": 18,
                "supply_dependency_score": 20,
                "continuity_readiness_score": 80,
                "substitutability_score": 72,
            },
        ],
        events=[
            {
                "event_id": "export-controls",
                "title": "Expanded export controls",
                "severity": "critical",
                "probability": 0.75,
                "velocity_score": 85,
                "exposure_ids": ["supplier-cn"],
                "status": "active",
                "mitigation_progress": 20,
                "response_readiness_score": 45,
            }
        ],
        continuity_options=[
            {
                "option_id": "dual-source",
                "name": "Dual-source critical components",
                "exposure_ids": ["supplier-cn"],
                "activation_readiness_score": 55,
                "lead_time_days": 120,
                "estimated_cost": 1_500_000,
                "capacity_coverage_score": 60,
            }
        ],
    )


def test_assessment_detects_vulnerable_exposures_and_priority_events() -> None:
    service = ExecutiveGeopoliticalService()
    item = service.create(payload())
    assessed = service.assess(item.id, "ws-1", "exec-1")
    assert assessed.assessment is not None
    assert "supplier-cn" in assessed.assessment.vulnerable_exposures
    assert "export-controls" in assessed.assessment.priority_events
    assert assessed.assessment.event_exposure_score > 0
    assert assessed.assessment.geopolitical_resilience_score < 100


def test_event_update_and_workspace_isolation() -> None:
    service = ExecutiveGeopoliticalService()
    item = service.create(payload())
    updated = service.update_event(
        item.id,
        "ws-1",
        GeopoliticalEventUpdate(
            event_id="export-controls",
            status="contained",
            mitigation_progress=85,
            response_readiness_score=82,
            actor_id="exec-2",
        ),
    )
    assert updated.events[0].mitigation_progress == 85
    assert updated.events[0].status == "contained"
    assert service.get(item.id, "other-workspace") is None
    assert len(service.audit_records("ws-1")) == 2


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveGeopoliticalService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_unknown_exposure_reference_is_rejected() -> None:
    data = payload().model_dump()
    data["events"][0]["exposure_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        GeopoliticalPortfolioCreate(**data)


def test_duplicate_exposure_ids_are_rejected() -> None:
    data = payload().model_dump()
    data["exposures"].append(data["exposures"][0])
    with pytest.raises(ValidationError):
        GeopoliticalPortfolioCreate(**data)
