from app.executive_market_intelligence_regime.models import (
    MacroEventInput,
    MarketIntelligenceCreate,
    MarketIntelligenceExecuteRequest,
    MarketIntelligenceState,
    MarketRegime,
    RiskEnvironment,
    TimeframeRegimeInput,
    TradePermission,
)
from app.executive_market_intelligence_regime.service import MarketIntelligenceRegimeService


def payload(**overrides) -> MarketIntelligenceCreate:
    data = dict(
        workspace_id="w-1",
        source_key="market-1",
        actor_id="tester",
        symbol="XAUUSD",
        asset_class="metals",
        timestamp_age_seconds=5,
        session="london",
        killzone_active=True,
        spread_bps=2,
        max_spread_bps=5,
        liquidity_score=85,
        atr_percentile=60,
        realized_volatility_percentile=65,
        timeframes=[
            TimeframeRegimeInput(timeframe="H4", regime=MarketRegime.TREND, trend_strength=80, volatility_percentile=60),
            TimeframeRegimeInput(timeframe="H1", regime=MarketRegime.TREND, trend_strength=75, volatility_percentile=65),
            TimeframeRegimeInput(timeframe="M15", regime=MarketRegime.TREND, trend_strength=70, volatility_percentile=60),
        ],
        required_regimes=[MarketRegime.TREND, MarketRegime.EXPANSION],
        risk_environment=RiskEnvironment.RISK_OFF,
        allowed_risk_environments=[RiskEnvironment.RISK_OFF, RiskEnvironment.NEUTRAL],
        gold_environment_score=85,
        correlation_score=0.3,
        account_risk_approved=True,
        prop_rules_approved=True,
    )
    data.update(overrides)
    return MarketIntelligenceCreate(**data)


def test_market_requires_human_approval_before_permission():
    service = MarketIntelligenceRegimeService()
    record = service.create(payload())
    assert record.state == MarketIntelligenceState.APPROVAL_REQUIRED
    assert record.permission == TradePermission.BLOCKED
    activated = service.execute(
        record.id,
        "w-1",
        MarketIntelligenceExecuteRequest(actor_id="tester", action="activate", human_approved=True),
    )
    assert activated.state == MarketIntelligenceState.TRADE_ALLOWED
    assert activated.permission == TradePermission.TRADE_ALLOWED


def test_high_impact_news_blocks_trading():
    service = MarketIntelligenceRegimeService()
    event = MacroEventInput(name="US CPI", impact="high", minutes_until_event=5, affected_currencies=["USD"])
    record = service.create(payload(macro_events=[event]))
    assert record.state == MarketIntelligenceState.NEWS_BLACKOUT
    assert record.permission == TradePermission.BLOCKED


def test_stale_data_and_risk_brain_fail_closed():
    service = MarketIntelligenceRegimeService()
    stale = service.create(payload(source_key="stale", timestamp_age_seconds=60, max_data_age_seconds=30))
    assert stale.state == MarketIntelligenceState.DATA_STALE
    blocked = service.create(payload(source_key="risk-block", upstream_risk_brain_blocked=True))
    assert blocked.state == MarketIntelligenceState.BLOCKED


def test_volatility_and_regime_guards():
    service = MarketIntelligenceRegimeService()
    volatility = service.create(payload(source_key="vol", realized_volatility_percentile=98))
    assert volatility.state == MarketIntelligenceState.VOLATILITY_REJECTED
    regime = service.create(payload(source_key="regime", required_regimes=[MarketRegime.RANGE]))
    assert regime.state == MarketIntelligenceState.REGIME_REJECTED


def test_workspace_isolation_and_duplicate_protection():
    service = MarketIntelligenceRegimeService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    try:
        service.create(payload())
        assert False
    except ValueError as exc:
        assert "duplicate" in str(exc)
