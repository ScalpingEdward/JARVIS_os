import pytest

from app.modules.incident_response_recovery.models import (
    IncidentAction,
    IncidentCreate,
    IncidentSeverity,
    IncidentState,
    RecoveryStep,
)
from app.modules.incident_response_recovery.service import IncidentResponseError, IncidentResponseService


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "incident-1",
        "title": "Broker position drift",
        "severity": IncidentSeverity.CRITICAL,
        "reconciliation_record_id": "recon-1",
        "runtime_record_id": "runtime-1",
        "command_record_ids": ["command-1"],
        "drift_codes": ["unexpected-position"],
        "recovery_steps": [RecoveryStep(step_id="freeze", action="freeze new commands")],
        "upstream_evidence_verified": True,
    }
    values.update(overrides)
    return IncidentCreate(**values)


def test_containment_recovery_monitoring_resolution_and_archive():
    service = IncidentResponseService()
    record = service.create(payload())
    assert record.state == IncidentState.CONTAINMENT_REQUIRED

    record = service.act(record.record_id, "ws-1", IncidentAction(action="approve", actor_id="operator", approval_token="approval-1"))
    assert record.state == IncidentState.APPROVED

    record = service.act(record.record_id, "ws-1", IncidentAction(action="contain", actor_id="operator", receipt_id="contain-1"))
    assert record.state == IncidentState.CONTAINED

    record = service.act(record.record_id, "ws-1", IncidentAction(action="start-recovery", actor_id="operator", receipt_id="recovery-1"))
    assert record.state == IncidentState.RECOVERY_IN_PROGRESS

    service.act(record.record_id, "ws-1", IncidentAction(action="complete-step", actor_id="operator", receipt_id="step-1", step_id="freeze"))
    record = service.act(record.record_id, "ws-1", IncidentAction(action="monitor", actor_id="operator", receipt_id="monitor-1"))
    assert record.state == IncidentState.MONITORING

    record = service.act(record.record_id, "ws-1", IncidentAction(action="resolve", actor_id="operator", receipt_id="resolve-1"))
    assert record.state == IncidentState.RESOLVED
    assert record.resolved_at is not None

    record = service.act(record.record_id, "ws-1", IncidentAction(action="archive", actor_id="operator"))
    assert record.state == IncidentState.ARCHIVED


def test_risk_brain_and_missing_evidence_are_hard_gates():
    service = IncidentResponseService()
    assert service.create(payload(source_key="blocked", risk_brain_blocked=True)).state == IncidentState.BLOCKED
    assert service.create(payload(source_key="missing", upstream_evidence_verified=False)).state == IncidentState.EVIDENCE_REQUIRED


def test_replay_protection_and_workspace_isolation():
    service = IncidentResponseService()
    record = service.create(payload())
    service.act(record.record_id, "ws-1", IncidentAction(action="approve", actor_id="operator", approval_token="token"))
    second = service.create(payload(source_key="incident-2"))
    with pytest.raises(IncidentResponseError, match="replay"):
        service.act(second.record_id, "ws-1", IncidentAction(action="approve", actor_id="operator", approval_token="token"))
    service.act(record.record_id, "ws-1", IncidentAction(action="contain", actor_id="operator", receipt_id="receipt"))
    with pytest.raises(IncidentResponseError, match="replay"):
        service.act(record.record_id, "ws-1", IncidentAction(action="start-recovery", actor_id="operator", receipt_id="receipt"))
    with pytest.raises(IncidentResponseError, match="not found"):
        service.get(record.record_id, "ws-2")


def test_incomplete_recovery_and_duplicate_inputs_are_rejected():
    service = IncidentResponseService()
    record = service.create(payload())
    service.act(record.record_id, "ws-1", IncidentAction(action="approve", actor_id="operator", approval_token="approval"))
    service.act(record.record_id, "ws-1", IncidentAction(action="contain", actor_id="operator", receipt_id="contain"))
    service.act(record.record_id, "ws-1", IncidentAction(action="start-recovery", actor_id="operator", receipt_id="recover"))
    with pytest.raises(IncidentResponseError, match="incomplete"):
        service.act(record.record_id, "ws-1", IncidentAction(action="monitor", actor_id="operator", receipt_id="monitor"))
    with pytest.raises(IncidentResponseError, match="duplicate source"):
        service.create(payload())
    with pytest.raises(ValueError, match="duplicate recovery step"):
        payload(source_key="dup", recovery_steps=[RecoveryStep(step_id="x", action="a"), RecoveryStep(step_id="x", action="b")])
