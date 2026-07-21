import pytest

from app.executive_autonomous_portfolio_governor.models import GovernorExecuteRequest, GovernorState, GovernorLimits, PortfolioGovernorCreate, PortfolioSnapshot
from app.executive_autonomous_portfolio_governor.service import AutonomousPortfolioGovernorService


def payload(**snapshot_overrides):
    snapshot = PortfolioSnapshot(
        account_equity=100000,
        daily_drawdown_pct=1,
        total_drawdown_pct=2,
        portfolio_heat_pct=3,
        margin_level_pct=500,
        correlated_exposure_pct=20,
        open_positions=2,
        spread_multiplier=1,
        broker_latency_ms=50,
        data_feed_healthy=True,
        vps_healthy=True,
        market_allowed_by_v19_08=True,
        shadow_validated_by_v19_09=True,
        journal_validated_by_v19_10=True,
        optimizer_approved_by_v19_11=True,
    ).model_copy(update=snapshot_overrides)
    return PortfolioGovernorCreate(
        workspace_id="ws-a",
        source_key="snapshot-1",
        actor_id="tester",
        account_risk_approved=True,
        prop_rules_approved=True,
        snapshot=snapshot,
        limits=GovernorLimits(
            max_daily_drawdown_pct=4,
            max_total_drawdown_pct=10,
            max_portfolio_heat_pct=6,
            min_margin_level_pct=150,
            max_correlated_exposure_pct=60,
            max_spread_multiplier=4,
            max_broker_latency_ms=500,
        ),
    )


def test_active_when_inside_limits():
    service = AutonomousPortfolioGovernorService()
    assert service.create(payload()).state == GovernorState.ACTIVE


def test_missing_evidence_fails_closed():
    service = AutonomousPortfolioGovernorService()
    record = service.create(payload(market_allowed_by_v19_08=False))
    assert record.state == GovernorState.EVIDENCE_REQUIRED


def test_hard_breach_triggers_kill_switch():
    service = AutonomousPortfolioGovernorService()
    record = service.create(payload(daily_drawdown_pct=4))
    assert record.state == GovernorState.KILL_SWITCH
    assert "daily-drawdown" in record.breaches


def test_recovery_requires_human_approval():
    service = AutonomousPortfolioGovernorService()
    record = service.create(payload(daily_drawdown_pct=4))
    record = service.execute(record.id, "ws-a", GovernorExecuteRequest(actor_id="tester", action="prepare-recovery"))
    with pytest.raises(ValueError, match="human approval"):
        service.execute(record.id, "ws-a", GovernorExecuteRequest(actor_id="tester", action="approve-recovery", human_approved=False))
    record = service.execute(record.id, "ws-a", GovernorExecuteRequest(actor_id="tester", action="approve-recovery", human_approved=True))
    assert record.state == GovernorState.RECOVERY_READY


def test_duplicate_source_key_and_workspace_isolation():
    service = AutonomousPortfolioGovernorService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="duplicate"):
        service.create(payload())
    assert service.get(record.id, "other") is None
