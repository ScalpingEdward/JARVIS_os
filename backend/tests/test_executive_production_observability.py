from app.executive_production_observability.models import (
    ObservabilityExecuteRequest,
    ObservabilityState,
    ProductionObservabilityCreate,
    RuntimeSnapshot,
)
from app.executive_production_observability.service import ProductionObservabilityService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="runtime-1",
        actor_id="master-brano",
        v20_06_deployment_healthy=True,
        snapshot=RuntimeSnapshot(
            service_name="jarvis-backend",
            release_version="20.07.0",
            environment="production",
            error_rate_pct=0.2,
            p95_latency_ms=250,
        ),
    )
    data.update(overrides)
    return ProductionObservabilityCreate(**data)


def test_healthy_runtime_is_recorded():
    service = ProductionObservabilityService()
    record = service.create(payload())
    assert record.state == ObservabilityState.HEALTHY


def test_degradation_opens_incident_and_can_recover():
    service = ProductionObservabilityService()
    snapshot = RuntimeSnapshot(
        service_name="jarvis-backend",
        release_version="20.07.0",
        environment="production",
        error_rate_pct=4,
        p95_latency_ms=250,
    )
    record = service.create(payload(snapshot=snapshot))
    assert record.state == ObservabilityState.INCIDENT_OPEN
    record = service.execute(record.id, "alpha", ObservabilityExecuteRequest(actor_id="master-brano", action="start-self-healing"))
    assert record.state == ObservabilityState.SELF_HEALING
    record = service.execute(
        record.id,
        "alpha",
        ObservabilityExecuteRequest(actor_id="master-brano", action="verify-recovery", recovery_checks_passed=True),
    )
    assert record.state == ObservabilityState.RECOVERED


def test_critical_incident_requires_human_approval():
    service = ProductionObservabilityService()
    snapshot = RuntimeSnapshot(
        service_name="jarvis-backend",
        release_version="20.07.0",
        environment="production",
        error_rate_pct=0,
        p95_latency_ms=200,
        data_feed_healthy=False,
    )
    record = service.create(payload(snapshot=snapshot))
    assert record.state == ObservabilityState.HUMAN_REVIEW_REQUIRED
    try:
        service.execute(record.id, "alpha", ObservabilityExecuteRequest(actor_id="master-brano", action="start-self-healing"))
        assert False, "expected human approval requirement"
    except ValueError:
        pass


def test_failed_recovery_requires_rollback():
    service = ProductionObservabilityService()
    snapshot = RuntimeSnapshot(
        service_name="jarvis-backend",
        release_version="20.07.0",
        environment="production",
        error_rate_pct=3,
        p95_latency_ms=200,
    )
    record = service.create(payload(snapshot=snapshot))
    record = service.execute(record.id, "alpha", ObservabilityExecuteRequest(actor_id="master-brano", action="start-self-healing"))
    record = service.execute(
        record.id,
        "alpha",
        ObservabilityExecuteRequest(actor_id="master-brano", action="verify-recovery", recovery_checks_passed=False),
    )
    assert record.state == ObservabilityState.ROLLBACK_REQUIRED


def test_missing_evidence_and_risk_brain_fail_closed():
    service = ProductionObservabilityService()
    assert service.create(payload(v20_06_deployment_healthy=False)).state == ObservabilityState.EVIDENCE_REQUIRED
    service = ProductionObservabilityService()
    assert service.create(payload(upstream_risk_brain_blocked=True)).state == ObservabilityState.BLOCKED


def test_duplicate_source_key_and_workspace_isolation():
    service = ProductionObservabilityService()
    first = service.create(payload())
    try:
        service.create(payload())
        assert False, "expected duplicate rejection"
    except ValueError:
        pass
    assert service.get(first.id, "other") is None
