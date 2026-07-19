import pytest
from pydantic import ValidationError

from app.executive_treasury.models import TreasuryPortfolioCreate, TreasuryRiskUpdate
from app.executive_treasury.service import ExecutiveTreasuryService


def payload(workspace_id: str = "ws-1", name: str = "Global treasury") -> TreasuryPortfolioCreate:
    return TreasuryPortfolioCreate(
        workspace_id=workspace_id,
        name=name,
        executive_owner_id="cfo-1",
        cash_positions=[
            {
                "position_id": "cash-eur",
                "entity": "EU HoldCo",
                "currency": "EUR",
                "available_cash": 12_000_000,
                "restricted_cash": 2_000_000,
                "forecast_accuracy_score": 62,
                "concentration_score": 75,
            }
        ],
        funding_sources=[
            {
                "source_id": "rcf-1",
                "name": "Revolving credit facility",
                "committed_amount": 20_000_000,
                "drawn_amount": 15_000_000,
                "maturity_months": 8,
                "interest_rate_percent": 5.2,
                "covenant_headroom_score": 48,
            }
        ],
        risks=[
            {
                "risk_id": "fx-gap",
                "title": "Unhedged USD exposure",
                "severity": "critical",
                "probability": 0.8,
                "impact_score": 85,
                "risk_type": "foreign_exchange",
                "remediation_progress": 20,
            }
        ],
        stress_scenarios=[
            {
                "scenario_id": "liquidity-freeze",
                "name": "Funding market freeze",
                "cash_outflow_percent": 35,
                "funding_reduction_percent": 50,
                "fx_shock_percent": 20,
                "survival_months": 5,
                "response_readiness_score": 52,
            }
        ],
        fx_hedge_coverage_score=45,
        interest_rate_hedge_coverage_score=60,
        counterparty_diversification_score=50,
    )


def test_assessment_detects_priority_risks_and_vulnerable_funding() -> None:
    service = ExecutiveTreasuryService()
    item = service.create(payload())
    assessed = service.assess(item.id, "ws-1", "cfo-1")
    assert assessed.assessment is not None
    assert "fx-gap" in assessed.assessment.priority_risks
    assert "rcf-1" in assessed.assessment.vulnerable_funding_sources
    assert assessed.assessment.risk_exposure_score > 0


def test_risk_update_and_workspace_isolation() -> None:
    service = ExecutiveTreasuryService()
    item = service.create(payload())
    updated = service.update_risk(item.id, "ws-1", TreasuryRiskUpdate(risk_id="fx-gap", remediation_progress=85, actor_id="cfo-2"))
    assert updated.risks[0].remediation_progress == 85
    assert service.get(item.id, "other-workspace") is None
    assert len(service.audit_records("ws-1")) == 2


def test_duplicate_portfolio_is_rejected() -> None:
    service = ExecutiveTreasuryService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_invalid_drawn_amount_is_rejected() -> None:
    data = payload().model_dump()
    data["funding_sources"][0]["drawn_amount"] = 25_000_000
    with pytest.raises(ValidationError):
        TreasuryPortfolioCreate(**data)
