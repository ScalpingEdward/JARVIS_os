import pytest

from app.executive_live_account_portfolio_state.models import AccountPortfolioRefreshRequest, AccountPortfolioSnapshotCreate, AccountPortfolioState
from app.executive_live_account_portfolio_state.service import LiveAccountPortfolioStateService


def payload(**overrides):
    data = dict(workspace_id="ws", source_key="snap-1", actor_id="tester", reconciliation_complete=True, account_login=123, balance=100000, equity=99500, margin=1000, free_margin=98500, margin_level=9950, floating_pl=-500, daily_pl=-500, weekly_pl=1000, monthly_pl=2500, equity_high_watermark=101000, daily_start_equity=100000, open_positions=2, pending_orders=1, gross_exposure=12000, risk_budget_used=500, risk_budget_limit=2000, daily_loss_limit=5000, max_loss_limit=10000, account_risk_approved=True, prop_rules_approved=True)
    data.update(overrides)
    return AccountPortfolioSnapshotCreate(**data)


def test_healthy_snapshot_and_metrics():
    service = LiveAccountPortfolioStateService()
    record = service.create(payload())
    assert record.state == AccountPortfolioState.HEALTHY
    assert record.current_drawdown_pct > 0
    assert record.portfolio_heat_pct == 25
    assert service.status("ws").healthy_records == 1


def test_requires_reconciliation():
    service = LiveAccountPortfolioStateService()
    record = service.create(payload(reconciliation_complete=False))
    assert record.state == AccountPortfolioState.SYNCHRONIZATION_REQUIRED


def test_risk_brain_fails_closed():
    service = LiveAccountPortfolioStateService()
    assert service.create(payload(risk_brain_blocked=True)).state == AccountPortfolioState.BLOCKED


def test_margin_warning():
    service = LiveAccountPortfolioStateService()
    assert service.create(payload(margin_level=200)).state == AccountPortfolioState.MARGIN_WARNING


def test_drawdown_critical():
    service = LiveAccountPortfolioStateService()
    record = service.create(payload(equity=94000, equity_high_watermark=100000))
    assert record.state == AccountPortfolioState.DRAWDOWN_CRITICAL


def test_prop_limit_breach():
    service = LiveAccountPortfolioStateService()
    record = service.create(payload(equity=89000, max_loss_limit=10000, drawdown_critical_pct=50))
    assert record.state == AccountPortfolioState.PROP_LIMIT_BREACHED


def test_critical_refresh_requires_human_approval():
    service = LiveAccountPortfolioStateService()
    record = service.create(payload(equity=94000, equity_high_watermark=100000))
    with pytest.raises(ValueError):
        service.refresh(record.id, "ws", AccountPortfolioRefreshRequest(actor_id="ops"))
    refreshed = service.refresh(record.id, "ws", AccountPortfolioRefreshRequest(actor_id="ops", human_approved=True))
    assert refreshed.id == record.id


def test_duplicate_and_workspace_isolation():
    service = LiveAccountPortfolioStateService()
    record = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(record.id, "other") is None
    assert len(service.list_records("ws")) == 1
    assert len(service.audit_records("ws")) == 1
