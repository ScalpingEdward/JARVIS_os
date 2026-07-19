from backend.app.executive_market.models import MarketPortfolioCreate, SignalUpdate
from backend.app.executive_market.service import ExecutiveMarketService


def payload(workspace_id: str = "ws-1") -> MarketPortfolioCreate:
    return MarketPortfolioCreate(
        workspace_id=workspace_id,
        name="Growth Markets",
        actor_id="ceo",
        segments=[
            {"segment_id": "s1", "name": "AI Automation", "market_size": 1000, "growth_rate": 25, "attractiveness": 90, "current_share": 5, "target_share": 15},
            {"segment_id": "s2", "name": "Legacy Tools", "market_size": 500, "growth_rate": -5, "attractiveness": 35, "current_share": 20, "target_share": 15},
        ],
        competitors=[
            {"competitor_id": "c1", "name": "Rival", "relative_strength": 80, "innovation_velocity": 85, "price_pressure": 70, "strategic_threat": 82}
        ],
        signals=[
            {"signal_id": "sig1", "signal_type": "technology", "direction": "negative", "confidence": 80, "impact": 75, "description": "Competitor launch"}
        ],
    )


def test_assessment_identifies_whitespace_and_threats():
    service = ExecutiveMarketService()
    item = service.create(payload())
    assessed = service.assess(item.portfolio_id, "ws-1", "ceo")
    assert "s1" in assessed.whitespace_segments
    assert "c1" in assessed.high_threat_competitors
    assert assessed.weighted_growth_rate > 0
    assert assessed.autonomous_actions_enabled is False


def test_workspace_isolation_and_signal_update():
    service = ExecutiveMarketService()
    item = service.create(payload())
    assert service.get(item.portfolio_id, "other") is None
    updated = service.update_signal(item.portfolio_id, "ws-1", SignalUpdate(actor_id="analyst", signal_id="sig1", confidence=90))
    assert updated.signals[0].confidence == 90


def test_duplicate_portfolio_rejected():
    service = ExecutiveMarketService()
    service.create(payload())
    try:
        service.create(payload())
        assert False
    except ValueError:
        assert True
