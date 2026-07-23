import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_63_alternative_data_intelligence_governance.models import (
    AlternativeDataAction,
    AlternativeDataCreate,
    AlternativeDataPolicy,
    AlternativeDataState,
    AlternativeSignal,
)
from backend.app.phoenix.v21_63_alternative_data_intelligence_governance.service import (
    AlternativeDataGovernanceService,
    GovernanceError,
)


def signal(**overrides):
    data = {
        "source_id": "source-a",
        "source_type": "web-traffic",
        "entity": "asset-a",
        "value": 120.0,
        "normalized_score": 20,
        "confidence": 85,
        "freshness_minutes": 30,
        "coverage_score": 80,
        "provenance_ref": "provider-a:obs-1",
    }
    data.update(overrides)
    return AlternativeSignal(**data)


def payload(**overrides):
    data = {
        "workspace_id": "workspace-a",
        "source_key": "alt-source-1",
        "subject_id": "asset-a",
        "signals": [signal()],
        "evidence_refs": ["macro-governance:record-1"],
        "policy": AlternativeDataPolicy(stable_cycles_required=2),
    }
    data.update(overrides)
    return AlternativeDataCreate(**data)


def advance(service, record_id):
    actions = [
        ("prepare-evidence", {}),
        ("score", {}),
        ("prepare-policy", {}),
        ("request-review", {}),
        ("approve", {"approval_token": "approval-1"}),
        ("activate", {"operation_receipt": "activate-1"}),
    ]
    for action, extra in actions:
        service.act(record_id, "workspace-a", AlternativeDataAction(action=action, actor="operator", **extra))


def test_full_alternative_data_lifecycle():
    service = AlternativeDataGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    for _ in range(2):
        service.act(record.record_id, "workspace-a", AlternativeDataAction(action="observe", actor="monitor", signals=[signal()]))
    assert record.state == AlternativeDataState.STABLE
    service.act(record.record_id, "workspace-a", AlternativeDataAction(action="confirm-stable", actor="operator", operation_receipt="stable-1"))
    assert record.state == AlternativeDataState.STABLE
    assert record.data_quality_score > 0
    assert service.audit


def test_large_signal_shift_and_bad_data_escalate():
    service = AlternativeDataGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    changed = signal(normalized_score=-90, confidence=20, coverage_score=20, freshness_minutes=4000)
    service.act(record.record_id, "workspace-a", AlternativeDataAction(action="observe", actor="monitor", signals=[changed]))
    assert record.state == AlternativeDataState.ESCALATED
    assert "confidence_below_minimum" in record.violations


def test_replay_risk_block_duplicates_and_isolation():
    service = AlternativeDataGovernanceService()
    first = service.create(payload())
    advance(service, first.record_id)
    second = service.create(payload(source_key="alt-source-2", subject_id="asset-b"))
    for action in ["prepare-evidence", "score", "prepare-policy", "request-review"]:
        service.act(second.record_id, "workspace-a", AlternativeDataAction(action=action, actor="operator"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "workspace-a", AlternativeDataAction(action="approve", actor="operator", approval_token="approval-1"))
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(first.record_id, "workspace-b")
    blocked = service.create(payload(source_key="alt-source-3", risk_brain_blocked=True))
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(blocked.record_id, "workspace-a", AlternativeDataAction(action="prepare-evidence", actor="operator"))


def test_validation_rejects_duplicate_sources_and_bad_policy():
    with pytest.raises(ValidationError):
        AlternativeDataCreate(
            workspace_id="w",
            source_key="s",
            subject_id="x",
            signals=[signal(), signal()],
        )
    with pytest.raises(ValidationError):
        AlternativeDataPolicy(signal_shift_threshold=80, escalation_threshold=70)
