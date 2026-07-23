import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_65_institutional_flow_intelligence.models import (
    FlowAction, FlowCreate, FlowPolicy, FlowState, InstitutionalFlowSignal,
)
from backend.app.phoenix.v21_65_institutional_flow_intelligence.service import (
    GovernanceError, InstitutionalFlowGovernanceService,
)


def signal(**overrides):
    data = {
        "signal_id": "flow-1", "asset": "SPY", "venue": "NYSE",
        "source_type": "etf-flow", "direction": "inflow", "notional_usd": 250_000_000,
        "participation_pct": 45, "persistence_score": 70, "concentration_score": 40,
        "confidence": 80, "freshness": 90, "provenance_score": 85,
    }
    data.update(overrides)
    return InstitutionalFlowSignal(**data)


def payload(**overrides):
    data = {
        "workspace_id": "workspace-a", "source_key": "institutional-flow-1",
        "universe": "US-equities", "signals": [signal()],
        "evidence_refs": ["macro:record-1", "news:record-1"],
        "policy": FlowPolicy(stable_cycles_required=2),
    }
    data.update(overrides)
    return FlowCreate(**data)


def advance(service, record_id):
    actions = [
        ("prepare-evidence", {}), ("score", {}), ("prepare-policy", {}),
        ("request-review", {}), ("approve", {"approval_token": "approval-1"}),
        ("activate", {"operation_receipt": "activation-1"}),
    ]
    for action, extra in actions:
        service.act(record_id, "workspace-a", FlowAction(action=action, actor="operator", **extra))


def test_full_institutional_flow_lifecycle():
    service = InstitutionalFlowGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    assert record.state == FlowState.ACTIVE
    for _ in range(2):
        service.act(record.record_id, "workspace-a", FlowAction(action="observe", actor="monitor", signals=[signal()]))
    assert record.state == FlowState.STABLE
    assert record.net_flow_score > 0
    assert service.audit


def test_flow_shift_and_escalation():
    service = InstitutionalFlowGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    outflow = signal(direction="outflow", participation_pct=85, persistence_score=90, confidence=95)
    service.act(record.record_id, "workspace-a", FlowAction(action="observe", actor="monitor", signals=[outflow]))
    assert record.state in {FlowState.FLOW_SHIFT, FlowState.ESCALATED}

    service = InstitutionalFlowGovernanceService()
    record = service.create(payload(source_key="institutional-flow-2"))
    advance(service, record.record_id)
    concentrated = signal(participation_pct=100, persistence_score=100, concentration_score=95, confidence=100)
    service.act(record.record_id, "workspace-a", FlowAction(action="observe", actor="monitor", signals=[concentrated]))
    assert record.state == FlowState.ESCALATED
    assert "concentration_exceeded" in record.violations


def test_replay_risk_block_duplicates_and_isolation():
    service = InstitutionalFlowGovernanceService()
    first = service.create(payload())
    advance(service, first.record_id)
    second = service.create(payload(source_key="institutional-flow-2"))
    for action in ["prepare-evidence", "score", "prepare-policy", "request-review"]:
        service.act(second.record_id, "workspace-a", FlowAction(action=action, actor="operator"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "workspace-a", FlowAction(action="approve", actor="operator", approval_token="approval-1"))
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(first.record_id, "workspace-b")
    blocked = service.create(payload(source_key="blocked", risk_brain_blocked=True))
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(blocked.record_id, "workspace-a", FlowAction(action="prepare-evidence", actor="operator"))


def test_validation():
    with pytest.raises(ValidationError):
        FlowPolicy(shift_threshold=80, escalation_threshold=70)
    with pytest.raises(ValidationError):
        FlowCreate(
            workspace_id="w", source_key="s", universe="u",
            signals=[signal(), signal()],
        )
