import pytest

from backend.app.phoenix.v21_56_live_alpha_capital_preservation.models import (
    LiveAlphaAction, LiveAlphaCreate, LiveAlphaState, PerformanceSnapshot, PreservationPolicy,
)
from backend.app.phoenix.v21_56_live_alpha_capital_preservation.service import (
    GovernanceError, LiveAlphaGovernanceService,
)


def snapshot(**overrides):
    data = dict(
        realized_alpha_pct=2.0,
        unrealized_alpha_pct=0.3,
        rolling_alpha_7d_pct=1.5,
        rolling_alpha_30d_pct=2.2,
        rolling_alpha_90d_pct=2.5,
        drawdown_pct=2.0,
        volatility_pct=4.0,
        sharpe=1.4,
        sortino=1.8,
        profit_factor=1.35,
        recovery_factor=2.0,
        liquidity_score=85,
        confidence=0.86,
    )
    data.update(overrides)
    return PerformanceSnapshot(**data)


def payload(workspace="w1", source="deploy-1", blocked=False):
    return LiveAlphaCreate(
        workspace_id=workspace,
        source_key=source,
        strategy_id="alpha-xau-01",
        deployed_capital=100000,
        snapshots=[snapshot()],
        policy=PreservationPolicy(healthy_cycles_required=2),
        evidence_refs=["v21.55:deployment:verified"],
        risk_brain_blocked=blocked,
    )


def advance_to_monitoring(service, record):
    actions = [
        LiveAlphaAction(action="prepare-evidence", actor="system"),
        LiveAlphaAction(action="analyze", actor="system"),
        LiveAlphaAction(action="request-review", actor="system"),
        LiveAlphaAction(action="approve", actor="human", approval_token="approval-1"),
        LiveAlphaAction(action="start-monitoring", actor="runtime", operation_receipt="monitor-1"),
    ]
    for action in actions:
        record = service.act(record.record_id, record.workspace_id, action)
    return record


def test_healthy_monitoring_reaches_healthy_state():
    service = LiveAlphaGovernanceService()
    record = advance_to_monitoring(service, service.create(payload()))
    record = service.act(record.record_id, "w1", LiveAlphaAction(action="observe", actor="monitor", snapshot=snapshot()))
    assert record.state == LiveAlphaState.MONITORING
    record = service.act(record.record_id, "w1", LiveAlphaAction(action="observe", actor="monitor", snapshot=snapshot()))
    assert record.state == LiveAlphaState.HEALTHY
    assert record.health_score >= record.policy.minimum_health_score


def test_drawdown_and_alpha_decay_escalate():
    service = LiveAlphaGovernanceService()
    record = advance_to_monitoring(service, service.create(payload()))
    bad = snapshot(rolling_alpha_7d_pct=-1.0, rolling_alpha_90d_pct=3.0, drawdown_pct=12.0, sharpe=-0.2, profit_factor=0.8)
    record = service.act(record.record_id, "w1", LiveAlphaAction(action="observe", actor="monitor", snapshot=bad))
    assert record.state == LiveAlphaState.ESCALATED
    assert "maximum_drawdown_exceeded" in record.violations
    assert "alpha_decay_detected" in record.violations


def test_capital_reduction_requires_receipt_and_halves_recommendation():
    service = LiveAlphaGovernanceService()
    record = advance_to_monitoring(service, service.create(payload()))
    bad = snapshot(drawdown_pct=12.0, sharpe=0.0, profit_factor=0.8)
    record = service.act(record.record_id, "w1", LiveAlphaAction(action="observe", actor="monitor", snapshot=bad))
    with pytest.raises(GovernanceError):
        service.act(record.record_id, "w1", LiveAlphaAction(action="reduce-capital", actor="human"))
    record = service.act(record.record_id, "w1", LiveAlphaAction(action="reduce-capital", actor="human", operation_receipt="reduce-1"))
    assert record.state == LiveAlphaState.CAPITAL_REDUCTION
    assert record.recommended_capital == 50000


def test_replay_protection_workspace_isolation_and_duplicate_source():
    service = LiveAlphaGovernanceService()
    first = service.create(payload())
    with pytest.raises(GovernanceError):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(first.record_id, "other")
    service.act(first.record_id, "w1", LiveAlphaAction(action="prepare-evidence", actor="system"))
    service.act(first.record_id, "w1", LiveAlphaAction(action="analyze", actor="system"))
    service.act(first.record_id, "w1", LiveAlphaAction(action="request-review", actor="system"))
    service.act(first.record_id, "w1", LiveAlphaAction(action="approve", actor="human", approval_token="same"))
    second = service.create(payload(source="deploy-2"))
    service.act(second.record_id, "w1", LiveAlphaAction(action="prepare-evidence", actor="system"))
    service.act(second.record_id, "w1", LiveAlphaAction(action="analyze", actor="system"))
    service.act(second.record_id, "w1", LiveAlphaAction(action="request-review", actor="system"))
    with pytest.raises(GovernanceError):
        service.act(second.record_id, "w1", LiveAlphaAction(action="approve", actor="human", approval_token="same"))


def test_risk_brain_hard_block_is_authoritative():
    service = LiveAlphaGovernanceService()
    record = service.create(payload(blocked=True))
    assert record.state == LiveAlphaState.BLOCKED
    with pytest.raises(GovernanceError):
        service.act(record.record_id, "w1", LiveAlphaAction(action="prepare-evidence", actor="system"))
    record = service.act(record.record_id, "w1", LiveAlphaAction(action="revoke", actor="risk-brain"))
    assert record.state == LiveAlphaState.REVOKED
