from app.executive_mt5_portfolio_correlation_exposure.models import (
    CorrelationPair,
    PortfolioExposureAssessmentCreate,
    PortfolioExposureExecuteRequest,
    PortfolioExposureState,
    PositionExposure,
)
from app.executive_mt5_portfolio_correlation_exposure.service import PortfolioCorrelationExposureService


def payload(**updates):
    base = dict(
        workspace_id="ws-a",
        source_key="source-1",
        actor_id="tester",
        trading_window_ready=True,
        snapshot_age_seconds=1,
        correlation_age_seconds=1,
        positions=[],
        correlations=[],
        proposed_symbol="XAUUSD",
        proposed_side="buy",
        proposed_notional=1000,
        proposed_risk_amount=50,
        proposed_base_currency="XAU",
        proposed_quote_currency="USD",
        max_symbol_notional=5000,
        max_currency_notional=10000,
        max_directional_notional=10000,
        max_portfolio_risk_amount=500,
        current_margin_level_percent=500,
        projected_margin_level_percent=400,
        account_risk_approved=True,
        prop_rules_approved=True,
        human_approved=True,
        rebalance_plan_defined=True,
    )
    base.update(updates)
    return PortfolioExposureAssessmentCreate(**base)


def test_requires_trading_window():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload(trading_window_ready=False))
    assert record.state == PortfolioExposureState.TRADING_WINDOW_REQUIRED


def test_rejects_stale_snapshot():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload(snapshot_age_seconds=99))
    assert record.state == PortfolioExposureState.SNAPSHOT_STALE


def test_rejects_stale_correlation_data():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload(correlation_age_seconds=999))
    assert record.state == PortfolioExposureState.CORRELATION_DATA_STALE


def test_rejects_symbol_exposure():
    service = PortfolioCorrelationExposureService()
    position = PositionExposure(symbol="XAUUSD", side="buy", volume=1, notional=4500, risk_amount=25, base_currency="XAU", quote_currency="USD")
    record = service.create(payload(positions=[position]))
    assert record.state == PortfolioExposureState.SYMBOL_EXPOSURE_EXCEEDED


def test_rejects_currency_exposure():
    service = PortfolioCorrelationExposureService()
    position = PositionExposure(symbol="EURUSD", side="buy", volume=1, notional=9500, risk_amount=25, base_currency="EUR", quote_currency="USD")
    record = service.create(payload(positions=[position]))
    assert record.state == PortfolioExposureState.CURRENCY_EXPOSURE_EXCEEDED


def test_rejects_directional_exposure():
    service = PortfolioCorrelationExposureService()
    position = PositionExposure(symbol="EURJPY", side="buy", volume=1, notional=9500, risk_amount=25, base_currency="EUR", quote_currency="JPY")
    record = service.create(payload(positions=[position]))
    assert record.state == PortfolioExposureState.DIRECTIONAL_EXPOSURE_EXCEEDED


def test_rejects_portfolio_risk():
    service = PortfolioCorrelationExposureService()
    position = PositionExposure(symbol="EURJPY", side="sell", volume=1, notional=1000, risk_amount=480, base_currency="EUR", quote_currency="JPY")
    record = service.create(payload(positions=[position]))
    assert record.state == PortfolioExposureState.PORTFOLIO_RISK_EXCEEDED


def test_rejects_high_correlation():
    service = PortfolioCorrelationExposureService()
    position = PositionExposure(symbol="XAGUSD", side="sell", volume=1, notional=1000, risk_amount=25, base_currency="XAG", quote_currency="USD")
    pair = CorrelationPair(symbol_a="XAUUSD", symbol_b="XAGUSD", coefficient=0.95)
    record = service.create(payload(positions=[position], correlations=[pair]))
    assert record.state == PortfolioExposureState.CORRELATION_LIMIT_EXCEEDED


def test_rejects_margin():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload(projected_margin_level_percent=120))
    assert record.state == PortfolioExposureState.MARGIN_REJECTED


def test_requires_approval_then_becomes_ready():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload(human_approved=False))
    assert record.state == PortfolioExposureState.APPROVAL_REQUIRED
    updated = service.execute(record.id, "ws-a", PortfolioExposureExecuteRequest(actor_id="approver", human_approved=True))
    assert updated.state == PortfolioExposureState.PORTFOLIO_READY


def test_risk_brain_hard_block():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload(risk_brain_blocked=True))
    assert record.state == PortfolioExposureState.BLOCKED


def test_duplicate_source_key_rejected():
    service = PortfolioCorrelationExposureService()
    service.create(payload())
    try:
        service.create(payload())
        assert False, "duplicate should fail"
    except ValueError:
        assert True


def test_workspace_isolation():
    service = PortfolioCorrelationExposureService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_records("ws-b") == []
