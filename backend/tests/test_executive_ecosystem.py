from app.executive_ecosystem.models import EcosystemPortfolioCreate, PartnershipUpdate
from app.executive_ecosystem.service import ExecutiveEcosystemService


def payload(workspace_id: str = "ws-1") -> EcosystemPortfolioCreate:
    return EcosystemPortfolioCreate(
        workspace_id=workspace_id,
        name="Strategic Ecosystem",
        actor_id="ceo",
        partners=[
            {
                "partner_id": "p1",
                "name": "Core Cloud Partner",
                "partnership_type": "technology",
                "annual_value": 1000,
                "joint_value_potential": 500,
                "strategic_alignment": 90,
                "performance_score": 82,
                "trust_score": 78,
                "dependency_level": "critical",
                "substitution_difficulty": 90,
                "contract_criticality": 88,
                "concentration_share": 60,
            },
            {
                "partner_id": "p2",
                "name": "Growth Channel",
                "partnership_type": "channel",
                "annual_value": 400,
                "joint_value_potential": 250,
                "strategic_alignment": 85,
                "performance_score": 88,
                "trust_score": 90,
                "dependency_level": "medium",
                "substitution_difficulty": 40,
                "contract_criticality": 45,
                "concentration_share": 25,
            },
        ],
        signals=[
            {
                "signal_id": "s1",
                "partner_id": "p1",
                "risk_probability": 65,
                "impact": 90,
                "opportunity_score": 55,
                "description": "Renewal and concentration exposure",
            }
        ],
    )


def test_assessment_detects_dependency_and_growth_partners():
    service = ExecutiveEcosystemService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-1", "ceo")
    assert "p1" in assessed.critical_partners
    assert "p2" in assessed.growth_partners
    assert assessed.concentration_risk_score == 60
    assert assessed.autonomous_actions_enabled is False


def test_workspace_isolation_and_partner_update():
    service = ExecutiveEcosystemService()
    item = service.create(payload())
    assert service.get(item.portfolio_id, "other") is None
    updated = service.update_partner(
        item.portfolio_id,
        "ws-1",
        PartnershipUpdate(actor_id="cpo", partner_id="p2", performance_score=94),
    )
    assert updated.partners[1].performance_score == 94


def test_duplicate_portfolio_rejected():
    service = ExecutiveEcosystemService()
    service.create(payload())
    try:
        service.create(payload())
        assert False
    except ValueError:
        assert True
