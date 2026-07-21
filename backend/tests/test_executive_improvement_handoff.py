import pytest

from app.executive_improvement_handoff.models import (
    BacklogEvidence,
    ImprovementHandoffCreate,
    ImprovementHandoffExecuteRequest,
    ImprovementHandoffState,
)
from app.executive_improvement_handoff.service import ImprovementHandoffService


def payload(**overrides):
    data = {
        "workspace_id": "alpha",
        "source_key": "backlog-1",
        "actor_id": "human-1",
        "v20_09_ready": True,
        "upstream_risk_brain_blocked": False,
        "evidence_digest": "abcdef1234567890",
        "evidence": BacklogEvidence(
            backlog_record_id="record-1",
            backlog_state="ready-for-v20.01",
            title="Add defensive feed watchdog",
            description="Create stale-feed detection with fail-closed behavior",
            priority_score=91,
            impact_score=88,
            confidence_score=84,
            effort_points=5,
            target_sprint="S42",
            dependencies=["market-data-adapter"],
            defensive_only=True,
            human_approved=True,
        ),
    }
    data.update(overrides)
    return ImprovementHandoffCreate(**data)


def test_ready_package_and_handoff_acceptance():
    service = ImprovementHandoffService()
    record = service.create(payload())
    assert record.state == ImprovementHandoffState.READY
    assert record.intake_package is not None
    assert record.intake_package.target_module == "v20.01"

    handed_off = service.execute(
        record.id,
        "alpha",
        ImprovementHandoffExecuteRequest(action="handoff", actor_id="human-1", human_approved=True),
    )
    assert handed_off.state == ImprovementHandoffState.HANDED_OFF
    assert handed_off.handoff_token

    accepted = service.execute(
        record.id,
        "alpha",
        ImprovementHandoffExecuteRequest(action="accept", actor_id="v20.01", v20_01_receipt_id="receipt-7"),
    )
    assert accepted.state == ImprovementHandoffState.ACCEPTED_BY_V20_01


def test_missing_v20_09_evidence_fails_closed():
    service = ImprovementHandoffService()
    record = service.create(payload(v20_09_ready=False))
    assert record.state == ImprovementHandoffState.EVIDENCE_REQUIRED


def test_risk_brain_block_has_precedence():
    service = ImprovementHandoffService()
    record = service.create(payload(upstream_risk_brain_blocked=True, v20_09_ready=False))
    assert record.state == ImprovementHandoffState.BLOCKED


def test_human_approval_evidence_required():
    service = ImprovementHandoffService()
    evidence = payload().evidence.model_copy(update={"human_approved": False})
    record = service.create(payload(evidence=evidence))
    assert record.state == ImprovementHandoffState.HUMAN_REVIEW_REQUIRED


def test_non_defensive_work_is_blocked():
    service = ImprovementHandoffService()
    evidence = payload().evidence.model_copy(update={"defensive_only": False})
    record = service.create(payload(evidence=evidence))
    assert record.state == ImprovementHandoffState.BLOCKED


def test_handoff_requires_explicit_human_approval():
    service = ImprovementHandoffService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(
            record.id,
            "alpha",
            ImprovementHandoffExecuteRequest(action="handoff", actor_id="agent", human_approved=False),
        )


def test_digest_and_source_key_cannot_be_reused():
    service = ImprovementHandoffService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(ValueError, match="evidence digest already consumed"):
        service.create(payload(source_key="backlog-2"))


def test_workspace_isolation_and_audit():
    service = ImprovementHandoffService()
    record = service.create(payload())
    assert service.get(record.id, "other") is None
    assert len(service.list_records("other")) == 0
    assert len(service.audit_records("alpha")) == 1
    assert service.status("alpha").ready_records == 1
