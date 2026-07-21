import pytest

from app.executive_incident_learning.models import (
    IncidentEvidence,
    IncidentLearningCreate,
    IncidentLearningExecuteRequest,
    IncidentLearningState,
)
from app.executive_incident_learning.service import IncidentLearningService


def payload(**overrides):
    evidence = IncidentEvidence(
        incident_id="inc-1",
        incident_state="recovered",
        severity="high",
        affected_components=["broker"],
        findings=["broker connectivity failed and recovery was verified"],
        remediation_actions=["restart connection"],
        recovery_verified=True,
        duration_seconds=300,
        recurrence_count=1,
    )
    data = {
        "workspace_id": "ws-1",
        "source_key": "source-1",
        "actor_id": "tester",
        "v20_07_incident_closed": True,
        "upstream_risk_brain_blocked": False,
        "evidence": evidence,
    }
    data.update(overrides)
    return IncidentLearningCreate(**data)


def test_code_change_improvement_requires_human_review():
    service = IncidentLearningService()
    record = service.create(payload())
    assert record.state == IncidentLearningState.HUMAN_REVIEW_REQUIRED
    assert record.root_causes[0].category == "broker-connectivity"
    assert record.improvements[0].defensive_only is True


def test_human_can_approve_defensive_improvement():
    service = IncidentLearningService()
    record = service.create(payload())
    result = service.execute(
        record.id,
        "ws-1",
        IncidentLearningExecuteRequest(action="approve", actor_id="human", human_approved=True),
    )
    assert result.state == IncidentLearningState.APPROVED


def test_missing_closed_incident_evidence_fails_closed():
    service = IncidentLearningService()
    record = service.create(payload(v20_07_incident_closed=False))
    assert record.state == IncidentLearningState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = IncidentLearningService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == IncidentLearningState.BLOCKED


def test_repeated_incident_requires_human_review():
    service = IncidentLearningService()
    evidence = payload().evidence.model_copy(update={
        "findings": ["unclassified repeated failure"],
        "recurrence_count": 4,
    })
    record = service.create(payload(source_key="repeat", evidence=evidence))
    assert record.state == IncidentLearningState.HUMAN_REVIEW_REQUIRED
    assert record.recurrence_risk_score > 50


def test_duplicate_source_key_rejected_per_workspace():
    service = IncidentLearningService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())


def test_workspace_isolation():
    service = IncidentLearningService()
    record = service.create(payload())
    assert service.get(record.id, "other-workspace") is None
    assert service.list_records("other-workspace") == []
