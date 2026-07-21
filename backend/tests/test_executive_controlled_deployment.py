from app.executive_controlled_deployment.models import (
    ControlledDeploymentCreate,
    DeploymentEvidence,
    DeploymentExecuteRequest,
    DeploymentState,
)
from app.executive_controlled_deployment.service import ControlledDeploymentService


def payload(**overrides):
    evidence = DeploymentEvidence(
        merge_commit_sha="abcdef1234567890",
        environment="staging",
        artifact_digest="sha256:0123456789abcdef",
        v20_05_verified=True,
        pre_deploy_ci_passed=True,
        tests_passed=True,
        secrets_validated=True,
        migrations_validated=True,
        rollback_verified=True,
    )
    data = dict(
        workspace_id="alpha",
        source_key="deploy-1",
        actor_id="master-brano",
        service_name="jarvis-backend",
        release_version="20.06.0",
        evidence=evidence,
    )
    data.update(overrides)
    return ControlledDeploymentCreate(**data)


def test_requires_human_approval():
    service = ControlledDeploymentService()
    record = service.create(payload())
    assert record.state == DeploymentState.APPROVAL_REQUIRED


def test_approved_deployment_becomes_healthy():
    service = ControlledDeploymentService()
    record = service.create(payload(human_approved=True))
    assert record.state == DeploymentState.READY
    record = service.execute(record.id, "alpha", DeploymentExecuteRequest(actor_id="master-brano", action="start-deployment", human_approved=True))
    assert record.state == DeploymentState.DEPLOYING
    record = service.execute(
        record.id,
        "alpha",
        DeploymentExecuteRequest(
            actor_id="master-brano",
            action="verify-runtime",
            runtime_health_passed=True,
            smoke_tests_passed=True,
            error_rate_pct=0.2,
            p95_latency_ms=250,
        ),
    )
    assert record.state == DeploymentState.HEALTHY


def test_runtime_failure_requires_rollback():
    service = ControlledDeploymentService()
    record = service.create(payload(human_approved=True))
    record = service.execute(record.id, "alpha", DeploymentExecuteRequest(actor_id="master-brano", action="start-deployment", human_approved=True))
    record = service.execute(
        record.id,
        "alpha",
        DeploymentExecuteRequest(
            actor_id="master-brano",
            action="verify-runtime",
            runtime_health_passed=False,
            smoke_tests_passed=False,
            error_rate_pct=10,
            p95_latency_ms=3000,
        ),
    )
    assert record.state == DeploymentState.ROLLBACK_REQUIRED
    record = service.execute(record.id, "alpha", DeploymentExecuteRequest(actor_id="master-brano", action="start-rollback"))
    assert record.state == DeploymentState.ROLLING_BACK
    record = service.execute(record.id, "alpha", DeploymentExecuteRequest(actor_id="master-brano", action="complete-rollback"))
    assert record.state == DeploymentState.ROLLED_BACK


def test_missing_v20_05_evidence_fails_closed():
    service = ControlledDeploymentService()
    request = payload()
    request.evidence.v20_05_verified = False
    record = service.create(request)
    assert record.state == DeploymentState.EVIDENCE_REQUIRED


def test_risk_brain_block_cannot_be_overridden():
    service = ControlledDeploymentService()
    record = service.create(payload(upstream_risk_brain_blocked=True, human_approved=True))
    assert record.state == DeploymentState.BLOCKED


def test_duplicate_source_key_and_workspace_isolation():
    service = ControlledDeploymentService()
    first = service.create(payload())
    try:
        service.create(payload())
        assert False, "expected duplicate rejection"
    except ValueError:
        pass
    assert service.get(first.id, "other") is None
