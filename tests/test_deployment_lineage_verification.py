import pytest

from backend.app.modules.deployment_lineage_verification.models import (
    CheckSeverity,
    DeploymentCheck,
    DeploymentVerificationCreate,
    VerificationAction,
    VerificationState,
)
from backend.app.modules.deployment_lineage_verification.service import (
    DeploymentLineageVerificationService,
    DeploymentVerificationError,
)


def payload(source_key: str = "rollout-1", drift: bool = False) -> DeploymentVerificationCreate:
    return DeploymentVerificationCreate(
        workspace_id="ws-a",
        source_key=source_key,
        rollout_id="r-29",
        runtime_id="runtime-1",
        previous_config_version="cfg-1",
        deployed_config_version="cfg-2",
        artifact_digest="sha256:abcdef123456",
        rollout_evidence_ref="v21.29:promoted",
        runtime_evidence_ref="v21.24:healthy",
        checks=[
            DeploymentCheck(
                check_id="config-version",
                component="runtime",
                expected_value="cfg-2",
                observed_value="cfg-1" if drift else "cfg-2",
                severity=CheckSeverity.CRITICAL,
            ),
            DeploymentCheck(
                check_id="artifact",
                component="package",
                expected_value="sha256:abcdef123456",
                observed_value="sha256:abcdef123456",
            ),
        ],
    )


def test_verified_deployment_and_lineage() -> None:
    service = DeploymentLineageVerificationService()
    record = service.create(payload())
    record = service.act("ws-a", record.record_id, VerificationAction(action="verify", actor_id="system"))
    assert record.state == VerificationState.VERIFIED
    assert record.lineage == ["cfg-1", "cfg-2"]
    assert record.drift_count == 0


def test_drift_approval_remediation_resolution() -> None:
    service = DeploymentLineageVerificationService()
    record = service.create(payload(drift=True))
    record = service.act("ws-a", record.record_id, VerificationAction(action="verify", actor_id="system"))
    assert record.state == VerificationState.HUMAN_REVIEW_REQUIRED
    assert record.critical_drift_count == 1
    record = service.act(
        "ws-a", record.record_id,
        VerificationAction(action="approve", actor_id="operator", approval_token="approval-1"),
    )
    record = service.act(
        "ws-a", record.record_id,
        VerificationAction(action="queue-remediation", actor_id="operator", receipt_id="queue-1"),
    )
    with pytest.raises(DeploymentVerificationError):
        service.act(
            "ws-a", record.record_id,
            VerificationAction(action="resolve", actor_id="operator", receipt_id="resolve-bad"),
        )
    record = service.act(
        "ws-a", record.record_id,
        VerificationAction(
            action="resolve",
            actor_id="operator",
            receipt_id="resolve-good",
            completed_check_ids=["config-version"],
        ),
    )
    assert record.state == VerificationState.RESOLVED


def test_governance_gates_replay_and_isolation() -> None:
    service = DeploymentLineageVerificationService()
    blocked = service.create(payload("blocked").model_copy(update={"risk_brain_blocked": True}))
    with pytest.raises(DeploymentVerificationError):
        service.act("ws-a", blocked.record_id, VerificationAction(action="verify", actor_id="system"))

    missing = service.create(payload("missing").model_copy(update={"runtime_evidence_ref": None}))
    assert missing.state == VerificationState.EVIDENCE_REQUIRED

    record = service.create(payload("drift", drift=True))
    service.act("ws-a", record.record_id, VerificationAction(action="verify", actor_id="system"))
    service.act(
        "ws-a", record.record_id,
        VerificationAction(action="approve", actor_id="operator", approval_token="token-1"),
    )
    second = service.create(payload("drift-2", drift=True))
    service.act("ws-a", second.record_id, VerificationAction(action="verify", actor_id="system"))
    with pytest.raises(DeploymentVerificationError):
        service.act(
            "ws-a", second.record_id,
            VerificationAction(action="approve", actor_id="operator", approval_token="token-1"),
        )
    with pytest.raises(DeploymentVerificationError):
        service.get("ws-b", record.record_id)
    with pytest.raises(DeploymentVerificationError):
        service.create(payload("drift"))
