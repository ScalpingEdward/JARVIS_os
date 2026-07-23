import pytest

from app.schemas.institutional_compliance import (
    ComplianceObservation,
    InstitutionalComplianceAction,
    InstitutionalComplianceCreate,
)
from app.services.institutional_compliance import InstitutionalComplianceService


def payload(source_key: str = "compliance-1", workspace_id: str = "ws-1") -> InstitutionalComplianceCreate:
    return InstitutionalComplianceCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        requested_by="analyst",
        required_jurisdictions=["EU"],
        observations=[
            ComplianceObservation(
                control_id="market-abuse-surveillance",
                domain="market-conduct",
                jurisdiction="EU",
                policy_coverage=0.95,
                evidence_completeness=0.92,
                control_effectiveness=0.90,
                disclosure_readiness=0.91,
                surveillance_coverage=0.94,
                recordkeeping_quality=0.93,
                confidence=0.98,
                freshness=0.99,
            )
        ],
    )


def test_scores_and_compliant_disposition() -> None:
    service = InstitutionalComplianceService()
    record = service.create(payload())
    assert record.scores.aggregate_compliance > 0.85
    assert record.assessments[0].disposition == "compliant"
    assert record.risk_flags == []


def test_detects_restriction_and_recordkeeping_gaps() -> None:
    service = InstitutionalComplianceService()
    data = payload()
    data.observations[0].restriction_breach_count = 1
    data.observations[0].recordkeeping_quality = 0.4
    record = service.create(data)
    assert "restriction-breach:market-abuse-surveillance" in record.risk_flags
    assert record.assessments[0].disposition == "restriction-alert"


def test_duplicate_source_key_is_blocked() -> None:
    service = InstitutionalComplianceService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source key"):
        service.create(payload())


def test_workspace_isolation() -> None:
    service = InstitutionalComplianceService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("other-workspace", record.record_id)


def test_human_approval_required_before_activation() -> None:
    service = InstitutionalComplianceService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.act(
            "ws-1",
            record.record_id,
            InstitutionalComplianceAction(action="activate", actor="operator", operation_id="op-1"),
        )


def test_approval_activation_and_replay_protection() -> None:
    service = InstitutionalComplianceService()
    record = service.create(payload())
    approved = service.act(
        "ws-1",
        record.record_id,
        InstitutionalComplianceAction(action="approve", actor="compliance-officer", operation_id="op-approve"),
    )
    assert approved.approved_by == "compliance-officer"
    active = service.act(
        "ws-1",
        record.record_id,
        InstitutionalComplianceAction(action="activate", actor="operator", operation_id="op-activate"),
    )
    assert active.state.value == "active"
    with pytest.raises(ValueError, match="operation replay detected"):
        service.act(
            "ws-1",
            record.record_id,
            InstitutionalComplianceAction(action="monitor", actor="operator", operation_id="op-activate"),
        )


def test_flags_block_approval() -> None:
    service = InstitutionalComplianceService()
    data = payload()
    data.observations[0].disclosure_readiness = 0.3
    record = service.create(data)
    with pytest.raises(ValueError, match="require remediation"):
        service.act(
            "ws-1",
            record.record_id,
            InstitutionalComplianceAction(action="approve", actor="compliance-officer", operation_id="op-2"),
        )
