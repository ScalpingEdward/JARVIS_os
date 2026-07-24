import pytest

from app.schemas.cybersecurity_privileged_access import CyberAccessGovernanceCreate, CyberAccessObservation, CyberAccessState
from app.services.cybersecurity_privileged_access import CybersecurityPrivilegedAccessService


def observation(**overrides):
    values = {
        "control_id": "iam-core",
        "domain": "identity-access",
        "asset_class": "trading-control-plane",
        "criticality": 0.80,
        "identity_assurance": 0.95,
        "mfa_coverage": 0.99,
        "least_privilege_coverage": 0.95,
        "privileged_session_monitoring": 0.95,
        "credential_hygiene": 0.95,
        "secret_rotation_coverage": 0.95,
        "network_segmentation": 0.90,
        "endpoint_protection": 0.95,
        "detection_coverage": 0.95,
        "response_readiness": 0.90,
        "logging_coverage": 0.95,
        "patch_compliance": 0.95,
        "open_critical_findings": 0,
        "stale_privileged_accounts": 0,
        "anomalous_access_events": 0,
        "confidence": 0.95,
        "freshness": 0.95,
    }
    values.update(overrides)
    return CyberAccessObservation(**values)


def payload(*observations, source_key="cyber-001"):
    return CyberAccessGovernanceCreate(
        workspace_id="ws-a",
        source_key=source_key,
        requested_by="security-governance",
        observations=list(observations or [observation()]),
    )


def test_secure_controls_score_without_flags():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation()))

    assert record.state == CyberAccessState.EVIDENCE_READY
    assert record.risk_flags == []
    assert record.scores.aggregate_security > 0.75
    assert record.dispositions[0].lifecycle_signal == "secure"


def test_identity_and_privilege_findings_are_governed():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation(
        mfa_coverage=0.60,
        least_privilege_coverage=0.60,
        stale_privileged_accounts=3,
    )))

    assert any(flag.startswith("identity-alert:") for flag in record.risk_flags)
    assert any(flag.startswith("privilege-alert:") for flag in record.risk_flags)
    disposition = record.dispositions[0]
    assert "identity-assurance-and-mfa-remediation" in disposition.required_actions
    assert "privileged-access-review" in disposition.required_actions


def test_credential_detection_and_response_gaps_generate_actions():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation(
        credential_hygiene=0.60,
        secret_rotation_coverage=0.50,
        detection_coverage=0.60,
        logging_coverage=0.60,
        response_readiness=0.50,
    )))

    actions = record.dispositions[0].required_actions
    assert "credential-and-secret-hygiene-review" in actions
    assert "detection-and-logging-coverage-review" in actions
    assert "incident-response-readiness-review" in actions


def test_critical_security_condition_triggers_risk_brain_hard_block():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation(
        criticality=0.98,
        open_critical_findings=1,
        anomalous_access_events=7,
    )))

    assert record.state == CyberAccessState.BLOCKED
    assert "risk-brain-hard-block" in record.risk_flags
    assert "risk-brain-hard-block" in record.dispositions[0].required_actions


def test_unresolved_findings_block_approval():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation(mfa_coverage=0.50)))

    with pytest.raises(ValueError, match="unresolved cybersecurity findings"):
        service.act("ws-a", record.record_id, "approve", "human-reviewer", "op-approve-1")


def test_human_approval_required_before_activation():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation()))

    with pytest.raises(ValueError, match="human approval required"):
        service.act("ws-a", record.record_id, "activate", "operator", "op-activate-1")

    approved = service.act("ws-a", record.record_id, "approve", "human-reviewer", "op-approve-2")
    assert approved.state == CyberAccessState.APPROVED
    active = service.act("ws-a", record.record_id, "activate", "operator", "op-activate-2")
    assert active.state == CyberAccessState.ACTIVE


def test_operation_replay_is_rejected():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation()))
    service.act("ws-a", record.record_id, "approve", "human-reviewer", "same-op")

    with pytest.raises(ValueError, match="operation replay detected"):
        service.act("ws-a", record.record_id, "monitor", "operator", "same-op")


def test_workspace_isolation():
    service = CybersecurityPrivilegedAccessService()
    record = service.create(payload(observation()))

    with pytest.raises(KeyError, match="record not found"):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected_per_workspace():
    service = CybersecurityPrivilegedAccessService()
    service.create(payload(observation(), source_key="same-source"))

    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload(observation(control_id="iam-secondary"), source_key="same-source"))


def test_status_preserves_advisory_only_boundary():
    service = CybersecurityPrivilegedAccessService()
    status = service.status()

    assert status["governance_only"] is True
    assert status["identity_mutation_enabled"] is False
    assert status["credential_mutation_enabled"] is False
    assert status["network_policy_mutation_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["human_approval_required"] is True
    assert status["risk_brain_authoritative"] is True
