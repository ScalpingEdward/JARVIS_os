import pytest

from backend.app.phoenix.v21_57_strategy_recovery_adaptive_revalidation.models import (
    RecoveryAction,
    RecoveryCreate,
    RecoveryIntervention,
    RecoveryObservation,
    RecoveryState,
    RevalidationGate,
)
from backend.app.phoenix.v21_57_strategy_recovery_adaptive_revalidation.service import (
    GovernanceError,
    StrategyRecoveryGovernanceService,
)


def observation(**overrides):
    values = {
        "alpha_pct": 1.8,
        "drawdown_pct": 1.0,
        "sharpe": 1.4,
        "profit_factor": 1.35,
        "win_rate_pct": 58,
        "execution_quality_score": 84,
        "regime_fit_score": 82,
        "liquidity_score": 85,
        "confidence": 0.86,
    }
    values.update(overrides)
    return RecoveryObservation(**values)


def payload(workspace_id="ws-1", source_key="source-1", blocked=False):
    return RecoveryCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        strategy_id="strategy-1",
        originating_live_alpha_record_id="live-alpha-1",
        baseline_capital=100000,
        observations=[observation()],
        interventions=[
            RecoveryIntervention(
                name="Reduce risk and add regime filter",
                category="risk-reduction",
                rationale="Stabilize recovery before capital return",
                expected_health_improvement=20,
            )
        ],
        gates=[
            RevalidationGate(name="walk-forward", score=90, minimum_score=80),
            RevalidationGate(name="stress-test", score=88, minimum_score=80),
        ],
        risk_brain_blocked=blocked,
    )


def advance_to_recovery(service, record):
    actions = [
        "prepare-evidence",
        "diagnose",
        "prepare-plan",
        "request-review",
    ]
    for action in actions:
        service.act(record.record_id, record.workspace_id, RecoveryAction(action=action, actor="tester"))
    service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(action="approve", actor="human", approval_token="approval-1"),
    )
    return service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(action="start-recovery", actor="orchestrator", operation_receipt="recovery-1"),
    )


def test_complete_recovery_revalidation_and_restore_lifecycle():
    service = StrategyRecoveryGovernanceService()
    record = advance_to_recovery(service, service.create(payload()))
    assert record.state == RecoveryState.RECOVERING

    for index in range(3):
        record = service.act(
            record.record_id,
            record.workspace_id,
            RecoveryAction(action="observe", actor="monitor", observation=observation(alpha_pct=2 + index)),
        )
    assert record.healthy_cycles == 3

    record = service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(action="start-revalidation", actor="validator", operation_receipt="revalidation-1"),
    )
    assert record.state == RecoveryState.REVALIDATING

    record = service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(action="complete-revalidation", actor="validator"),
    )
    assert record.state == RecoveryState.REVALIDATED
    assert record.revalidation_pass_rate == 1.0

    record = service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(
            action="authorize-conditional-return",
            actor="human",
            operation_receipt="conditional-return-1",
        ),
    )
    assert record.recommended_return_capital == 25000

    record = service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(action="restore", actor="human", operation_receipt="restore-1"),
    )
    assert record.state == RecoveryState.RESTORED
    assert record.recommended_return_capital == 100000


def test_unhealthy_observation_escalates():
    service = StrategyRecoveryGovernanceService()
    record = advance_to_recovery(service, service.create(payload()))
    record = service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(
            action="observe",
            actor="monitor",
            observation=observation(drawdown_pct=8, confidence=0.4),
        ),
    )
    assert record.state == RecoveryState.ESCALATED
    assert "maximum_recovery_drawdown_exceeded" in record.violations
    assert "confidence_below_minimum" in record.violations


def test_revalidation_requires_healthy_cycles():
    service = StrategyRecoveryGovernanceService()
    record = advance_to_recovery(service, service.create(payload()))
    with pytest.raises(GovernanceError, match="insufficient healthy recovery cycles"):
        service.act(
            record.record_id,
            record.workspace_id,
            RecoveryAction(action="start-revalidation", actor="validator", operation_receipt="too-early"),
        )


def test_failed_gate_blocks_revalidation_completion():
    service = StrategyRecoveryGovernanceService()
    record = advance_to_recovery(service, service.create(payload()))
    for _ in range(3):
        service.act(
            record.record_id,
            record.workspace_id,
            RecoveryAction(action="observe", actor="monitor", observation=observation()),
        )
    service.act(
        record.record_id,
        record.workspace_id,
        RecoveryAction(action="start-revalidation", actor="validator", operation_receipt="revalidation-2"),
    )
    failed_gate = record.gates[0].model_copy(update={"score": 20})
    with pytest.raises(GovernanceError, match="revalidation gates"):
        service.act(
            record.record_id,
            record.workspace_id,
            RecoveryAction(action="complete-revalidation", actor="validator", gate_updates=[failed_gate]),
        )


def test_replay_protection():
    service = StrategyRecoveryGovernanceService()
    first = service.create(payload(source_key="first"))
    second = service.create(payload(source_key="second"))
    for record in (first, second):
        for action in ["prepare-evidence", "diagnose", "prepare-plan", "request-review"]:
            service.act(record.record_id, record.workspace_id, RecoveryAction(action=action, actor="tester"))
    service.act(
        first.record_id,
        first.workspace_id,
        RecoveryAction(action="approve", actor="human", approval_token="same-token"),
    )
    with pytest.raises(GovernanceError, match="replay"):
        service.act(
            second.record_id,
            second.workspace_id,
            RecoveryAction(action="approve", actor="human", approval_token="same-token"),
        )


def test_risk_brain_block_is_authoritative():
    service = StrategyRecoveryGovernanceService()
    record = service.create(payload(blocked=True))
    assert record.state == RecoveryState.BLOCKED
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(
            record.record_id,
            record.workspace_id,
            RecoveryAction(action="prepare-evidence", actor="tester"),
        )


def test_duplicate_source_and_workspace_isolation():
    service = StrategyRecoveryGovernanceService()
    record = service.create(payload())
    with pytest.raises(GovernanceError, match="duplicate source_key"):
        service.create(payload())
    assert service.list("other-workspace") == []
    with pytest.raises(KeyError):
        service.get(record.record_id, "other-workspace")
    assert service.audit[0].workspace_id == "ws-1"
