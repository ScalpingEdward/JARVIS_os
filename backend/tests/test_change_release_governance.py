from app.schemas.change_release_governance import (
    ChangeObservation,
    ChangeReleaseGovernanceCreate,
    ChangeReleaseState,
)
from app.services.change_release_governance import ChangeReleaseGovernanceService


def healthy_payload(source_key: str = "release-healthy") -> ChangeReleaseGovernanceCreate:
    return ChangeReleaseGovernanceCreate(
        workspace_id="ws-1",
        source_key=source_key,
        requested_by="operator",
        observations=[
            ChangeObservation(
                change_id="chg-1",
                component="portfolio-ai-brain",
                criticality=0.8,
                test_coverage=0.95,
                regression_coverage=0.92,
                rollback_readiness=0.94,
                peer_review_coverage=0.95,
                segregation_of_duties=0.95,
                security_review_coverage=0.90,
                dependency_impact_known=0.94,
                observability_readiness=0.92,
                canary_readiness=0.90,
                deployment_rehearsal=0.88,
                open_blocking_findings=0,
                recent_failed_releases=0,
                confidence=0.95,
                freshness=0.95,
            )
        ],
    )


def test_healthy_change_scores_release_ready() -> None:
    service = ChangeReleaseGovernanceService()
    record = service.create(healthy_payload())
    assert record.state == ChangeReleaseState.EVIDENCE_READY
    assert record.risk_flags == []
    assert record.dispositions[0].lifecycle_signal == "release-ready"
    assert record.scores.aggregate_release_assurance > 0.75


def test_change_risk_generates_flags_and_actions() -> None:
    service = ChangeReleaseGovernanceService()
    payload = healthy_payload("release-risk")
    payload.observations[0] = payload.observations[0].model_copy(
        update={
            "test_coverage": 0.50,
            "rollback_readiness": 0.45,
            "security_review_coverage": 0.50,
            "observability_readiness": 0.45,
            "open_blocking_findings": 2,
        }
    )
    record = service.create(payload)
    assert any(flag.startswith("test-gap:") for flag in record.risk_flags)
    assert any(flag.startswith("rollback-gap:") for flag in record.risk_flags)
    assert any(flag.startswith("security-alert:") for flag in record.risk_flags)
    assert any(flag.startswith("change-risk-alert:") for flag in record.risk_flags)
    assert "change-advisory-board-review" in record.dispositions[0].required_actions


def test_critical_change_can_trigger_risk_brain_hard_block() -> None:
    service = ChangeReleaseGovernanceService()
    payload = healthy_payload("release-blocked")
    payload.observations[0] = payload.observations[0].model_copy(
        update={
            "criticality": 0.98,
            "rollback_readiness": 0.20,
            "open_blocking_findings": 3,
        }
    )
    record = service.create(payload)
    assert record.state == ChangeReleaseState.BLOCKED
    assert "risk-brain-hard-block" in record.risk_flags


def test_unresolved_flags_block_approval() -> None:
    service = ChangeReleaseGovernanceService()
    payload = healthy_payload("release-approval-block")
    payload.observations[0] = payload.observations[0].model_copy(update={"test_coverage": 0.40})
    record = service.create(payload)
    try:
        service.act("ws-1", record.record_id, "approve", "reviewer", "op-approve")
    except ValueError as exc:
        assert "unresolved change-governance flags" in str(exc)
    else:
        raise AssertionError("approval should have been blocked")


def test_human_approval_required_before_activation() -> None:
    service = ChangeReleaseGovernanceService()
    record = service.create(healthy_payload("release-human-approval"))
    try:
        service.act("ws-1", record.record_id, "activate", "operator", "op-activate")
    except ValueError as exc:
        assert "human approval required" in str(exc)
    else:
        raise AssertionError("activation should have required approval")


def test_approve_then_activate_and_audit() -> None:
    service = ChangeReleaseGovernanceService()
    record = service.create(healthy_payload("release-approved"))
    approved = service.act("ws-1", record.record_id, "approve", "reviewer", "op-1")
    assert approved.state == ChangeReleaseState.APPROVED
    active = service.act("ws-1", record.record_id, "activate", "operator", "op-2")
    assert active.state == ChangeReleaseState.ACTIVE
    assert len(service.audit("ws-1")) == 3


def test_operation_replay_is_rejected() -> None:
    service = ChangeReleaseGovernanceService()
    record = service.create(healthy_payload("release-replay"))
    service.act("ws-1", record.record_id, "approve", "reviewer", "same-op")
    try:
        service.act("ws-1", record.record_id, "monitor", "reviewer", "same-op")
    except ValueError as exc:
        assert "operation replay detected" in str(exc)
    else:
        raise AssertionError("replay should have been rejected")


def test_workspace_isolation_and_duplicate_source_key() -> None:
    service = ChangeReleaseGovernanceService()
    record = service.create(healthy_payload("release-isolation"))
    assert service.list("other-workspace") == []
    try:
        service.get("other-workspace", record.record_id)
    except KeyError:
        pass
    else:
        raise AssertionError("cross-workspace lookup should fail")

    try:
        service.create(healthy_payload("release-isolation"))
    except ValueError as exc:
        assert "duplicate source_key" in str(exc)
    else:
        raise AssertionError("duplicate source key should fail")


def test_status_exposes_safety_boundary() -> None:
    status = ChangeReleaseGovernanceService().status()
    assert status["governance_only"] is True
    assert status["deployment_mutation_enabled"] is False
    assert status["release_execution_enabled"] is False
    assert status["rollback_execution_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True
