import pytest

from app.modules.strategy_governance_policy_engine.models import (
    GovernanceAction,
    GovernanceCommand,
    GovernanceState,
    StrategyPolicyCreate,
    TradingWindow,
)
from app.modules.strategy_governance_policy_engine.service import (
    GovernanceError,
    StrategyGovernanceService,
)


def payload(**overrides):
    data = {
        "workspace_id": "ws-1",
        "source_key": "src-1",
        "optimizer_record_id": "opt-1",
        "strategy_id": "smc-xau",
        "policy_version": 1,
        "symbols_allowed": ["XAUUSD"],
        "symbols_blocked": [],
        "sessions_allowed": ["london", "new-york"],
        "setup_grades_allowed": ["A+", "A"],
        "minimum_confidence": 75,
        "max_risk_per_trade_percent": 0.5,
        "max_daily_risk_percent": 2.0,
        "max_open_positions": 2,
        "minimum_sample_size": 10,
        "observed_sample_size": 30,
        "trading_windows": [TradingWindow(weekday=0, start_minute_utc=420, end_minute_utc=1020)],
        "upstream_evidence_verified": True,
        "risk_brain_blocked": False,
    }
    data.update(overrides)
    return StrategyPolicyCreate(**data)


def test_clean_policy_approval_and_activation():
    service = StrategyGovernanceService()
    record = service.create(payload())
    assert record.state == GovernanceState.POLICY_READY

    approved = service.act(
        "ws-1",
        record.id,
        GovernanceAction(command=GovernanceCommand.APPROVE, actor="master", approval_token="approve-1"),
    )
    assert approved.state == GovernanceState.APPROVED

    active = service.act(
        "ws-1",
        record.id,
        GovernanceAction(command=GovernanceCommand.ACTIVATE, actor="master", activation_receipt="activate-1"),
    )
    assert active.state == GovernanceState.ACTIVATED
    assert service.active_policy("ws-1", "smc-xau").policy_version == 1


def test_missing_evidence_and_risk_brain_fail_closed():
    service = StrategyGovernanceService()
    missing = service.create(payload(source_key="src-missing", upstream_evidence_verified=False))
    blocked = service.create(payload(source_key="src-blocked", policy_version=2, risk_brain_blocked=True))
    assert missing.state == GovernanceState.EVIDENCE_REQUIRED
    assert blocked.state == GovernanceState.BLOCKED


def test_policy_violation_prevents_approval():
    service = StrategyGovernanceService()
    record = service.create(
        payload(symbols_blocked=["XAUUSD"], max_daily_risk_percent=0.25)
    )
    assert record.state == GovernanceState.POLICY_REVIEW_REQUIRED
    assert record.assessment and record.assessment.violations
    with pytest.raises(GovernanceError):
        service.act(
            "ws-1",
            record.id,
            GovernanceAction(command=GovernanceCommand.APPROVE, actor="master", approval_token="bad"),
        )


def test_replay_duplicate_and_workspace_isolation():
    service = StrategyGovernanceService()
    first = service.create(payload())
    with pytest.raises(GovernanceError):
        service.create(payload())
    with pytest.raises(GovernanceError):
        service.get("other-workspace", first.id)

    second = service.create(payload(source_key="src-2", policy_version=2))
    service.act(
        "ws-1",
        first.id,
        GovernanceAction(command=GovernanceCommand.APPROVE, actor="master", approval_token="same-token"),
    )
    with pytest.raises(GovernanceError):
        service.act(
            "ws-1",
            second.id,
            GovernanceAction(command=GovernanceCommand.APPROVE, actor="master", approval_token="same-token"),
        )


def test_rollback_to_previous_active_version():
    service = StrategyGovernanceService()
    one = service.create(payload())
    service.act("ws-1", one.id, GovernanceAction(command=GovernanceCommand.APPROVE, actor="master", approval_token="a1"))
    service.act("ws-1", one.id, GovernanceAction(command=GovernanceCommand.ACTIVATE, actor="master", activation_receipt="r1"))

    two = service.create(payload(source_key="src-2", policy_version=2))
    service.act("ws-1", two.id, GovernanceAction(command=GovernanceCommand.APPROVE, actor="master", approval_token="a2"))
    service.act("ws-1", two.id, GovernanceAction(command=GovernanceCommand.ACTIVATE, actor="master", activation_receipt="r2"))
    rolled = service.act(
        "ws-1",
        two.id,
        GovernanceAction(command=GovernanceCommand.ROLLBACK, actor="master", rollback_target_version=1),
    )
    assert rolled.state == GovernanceState.ROLLED_BACK
    assert service.active_policy("ws-1", "smc-xau").policy_version == 1
