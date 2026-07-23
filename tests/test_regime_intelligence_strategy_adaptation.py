import pytest

from backend.app.phoenix.v21_58_regime_intelligence_strategy_adaptation.models import (
    AdaptationDirective,
    RegimeAction,
    RegimeCreate,
    RegimeObservation,
    RegimeState,
)
from backend.app.phoenix.v21_58_regime_intelligence_strategy_adaptation.service import (
    GovernanceError,
    RegimeGovernanceService,
)


def observation(**overrides):
    data = {
        "trend_score": 70,
        "volatility_score": 35,
        "liquidity_score": 80,
        "dispersion_score": 45,
        "correlation_score": 40,
        "stress_score": 25,
        "confidence": 0.9,
    }
    data.update(overrides)
    return RegimeObservation(**data)


def payload(workspace="ws-1", source="src-1", blocked=False):
    return RegimeCreate(
        workspace_id=workspace,
        source_key=source,
        strategy_ids=["strategy-a"],
        observations=[observation()],
        directives=[AdaptationDirective(
            strategy_id="strategy-a",
            parameter="regime-filter",
            current_value="neutral",
            proposed_value="stable-trend",
            rationale="align strategy with classified regime",
            confidence=0.85,
        )],
        evidence_refs=["evidence://regime/1"],
        risk_brain_blocked=blocked,
    )


def advance_to_monitoring(service, record):
    actions = [
        ("prepare-evidence", {}),
        ("classify", {}),
        ("prepare-adaptation", {}),
        ("request-review", {}),
        ("approve", {"approval_token": "approval-1"}),
        ("start-adaptation", {"operation_receipt": "adapt-1"}),
    ]
    for action, extra in actions:
        record = service.act(record.record_id, record.workspace_id, RegimeAction(action=action, actor="tester", **extra))
    return record


def test_full_validation_lifecycle():
    service = RegimeGovernanceService()
    record = advance_to_monitoring(service, service.create(payload()))
    assert record.state is RegimeState.ADAPTING
    for _ in range(record.policy.validation_cycles_required):
        record = service.act(record.record_id, "ws-1", RegimeAction(action="observe", actor="monitor", observation=observation()))
    record = service.act(record.record_id, "ws-1", RegimeAction(action="validate", actor="reviewer", operation_receipt="validate-1"))
    assert record.state is RegimeState.VALIDATED
    assert record.regime_label == "stable-trend"


def test_regime_shift_and_stress_escalation():
    service = RegimeGovernanceService()
    record = advance_to_monitoring(service, service.create(payload()))
    shifted = observation(trend_score=10, volatility_score=95, liquidity_score=30, stress_score=90)
    record = service.act(record.record_id, "ws-1", RegimeAction(action="observe", actor="monitor", observation=shifted))
    assert record.state is RegimeState.ESCALATED
    assert "stress_above_maximum" in record.violations


def test_replay_protection():
    service = RegimeGovernanceService()
    first = service.create(payload(source="one"))
    for action in ["prepare-evidence", "classify", "prepare-adaptation", "request-review"]:
        first = service.act(first.record_id, "ws-1", RegimeAction(action=action, actor="tester"))
    service.act(first.record_id, "ws-1", RegimeAction(action="approve", actor="tester", approval_token="shared"))
    second = service.create(payload(source="two"))
    for action in ["prepare-evidence", "classify", "prepare-adaptation", "request-review"]:
        second = service.act(second.record_id, "ws-1", RegimeAction(action=action, actor="tester"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "ws-1", RegimeAction(action="approve", actor="tester", approval_token="shared"))


def test_risk_block_duplicate_and_workspace_isolation():
    service = RegimeGovernanceService()
    blocked = service.create(payload(blocked=True))
    assert blocked.state is RegimeState.BLOCKED
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(blocked.record_id, "ws-1", RegimeAction(action="prepare-evidence", actor="tester"))
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(blocked.record_id, "other-workspace")


def test_validation_requires_healthy_cycles():
    service = RegimeGovernanceService()
    record = advance_to_monitoring(service, service.create(payload()))
    record = service.act(record.record_id, "ws-1", RegimeAction(action="observe", actor="monitor", observation=observation()))
    with pytest.raises(GovernanceError, match="insufficient"):
        service.act(record.record_id, "ws-1", RegimeAction(action="validate", actor="reviewer", operation_receipt="validate-early"))
