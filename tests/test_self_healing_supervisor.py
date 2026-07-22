import pytest
from pydantic import ValidationError

from backend.app.modules.self_healing_supervisor.models import (
    HealthSignal,
    HealthStatus,
    RecoveryCandidate,
    RiskDecision,
    SignalSeverity,
    SupervisorActionRequest,
    SupervisorCreate,
    SupervisorState,
)
from backend.app.modules.self_healing_supervisor.service import (
    SelfHealingSupervisorError,
    SelfHealingSupervisorService,
)


def signal(signal_id: str = "sig-1", status: HealthStatus = HealthStatus.DEGRADED) -> HealthSignal:
    return HealthSignal(
        signal_id=signal_id,
        source="runtime-supervisor",
        metric="heartbeat-lag",
        status=status,
        severity=SignalSeverity.CRITICAL if status == HealthStatus.CRITICAL else SignalSeverity.WARNING,
        observed_value=12,
        threshold=5,
        evidence_refs=[f"evidence:{signal_id}"],
    )


def candidate() -> RecoveryCandidate:
    return RecoveryCandidate(
        candidate_id="candidate-1",
        orchestration_id="orch-verified-1",
        trigger_signal_ids=["sig-1"],
        expected_outcome="restore runtime health",
        confidence=0.93,
        blast_radius="single-runtime-worker",
        evidence_refs=["evidence:candidate-1"],
    )


def payload(workspace: str = "ws-1", source_key: str = "source-1", risk: RiskDecision = RiskDecision.ALLOW) -> SupervisorCreate:
    return SupervisorCreate(
        workspace_id=workspace,
        source_key=source_key,
        target_system="execution-runtime",
        health_signals=[signal()],
        recovery_candidates=[candidate()],
        required_healthy_cycles=2,
        max_recovery_attempts=2,
        monitoring_evidence_refs=["evidence:monitoring"],
        risk_decision=risk,
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, SupervisorActionRequest(action=action, actor="operator", **kwargs))


def test_full_self_healing_lifecycle():
    service = SelfHealingSupervisorService()
    record = service.create(payload())
    assert act(service, record, "start-monitoring").state == SupervisorState.DEGRADED
    assert act(service, record, "propose-recovery", candidate_id="candidate-1").state == SupervisorState.RECOVERY_PROPOSED
    assert act(service, record, "request-review").state == SupervisorState.HUMAN_REVIEW_REQUIRED
    assert act(service, record, "approve", approval_token="approval-1").state == SupervisorState.APPROVED
    assert act(service, record, "start-recovery", receipt_id="start-1").state == SupervisorState.RECOVERING
    assert act(service, record, "record-cycle", healthy_cycle=True).state == SupervisorState.STABILIZING
    stabilized = act(service, record, "record-cycle", healthy_cycle=True)
    assert stabilized.consecutive_healthy_cycles == 2
    healthy = act(service, record, "complete-recovery", receipt_id="complete-1", recovery_evidence_refs=["evidence:recovered"])
    assert healthy.state == SupervisorState.HEALTHY
    assert act(service, record, "archive").state == SupervisorState.ARCHIVED


def test_requires_human_approval_and_stabilization():
    service = SelfHealingSupervisorService()
    record = service.create(payload())
    act(service, record, "start-monitoring")
    act(service, record, "propose-recovery", candidate_id="candidate-1")
    with pytest.raises(SelfHealingSupervisorError):
        act(service, record, "start-recovery", receipt_id="early")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval")
    act(service, record, "start-recovery", receipt_id="start")
    act(service, record, "record-cycle", healthy_cycle=True)
    with pytest.raises(SelfHealingSupervisorError):
        act(service, record, "complete-recovery", receipt_id="complete", recovery_evidence_refs=["evidence"])


def test_risk_brain_block_is_authoritative():
    service = SelfHealingSupervisorService()
    record = service.create(payload(risk=RiskDecision.BLOCK))
    blocked = act(service, record, "start-monitoring")
    assert blocked.state == SupervisorState.BLOCKED
    with pytest.raises(SelfHealingSupervisorError):
        act(service, record, "propose-recovery", candidate_id="candidate-1")


def test_replay_and_duplicate_protection():
    service = SelfHealingSupervisorService()
    record = service.create(payload())
    with pytest.raises(SelfHealingSupervisorError):
        service.create(payload())
    act(service, record, "start-monitoring")
    duplicate = signal("sig-1", HealthStatus.CRITICAL)
    with pytest.raises(SelfHealingSupervisorError):
        act(service, record, "ingest-signal", signal=duplicate)
    act(service, record, "propose-recovery", candidate_id="candidate-1")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="token-1")
    second = service.create(payload(source_key="source-2"))
    act(service, second, "start-monitoring")
    act(service, second, "propose-recovery", candidate_id="candidate-1")
    act(service, second, "request-review")
    with pytest.raises(SelfHealingSupervisorError):
        act(service, second, "approve", approval_token="token-1")


def test_workspace_isolation_and_audit():
    service = SelfHealingSupervisorService()
    record = service.create(payload())
    with pytest.raises(SelfHealingSupervisorError):
        service.get(record.record_id, "other-workspace")
    assert len(service.list("ws-1")) == 1
    assert len(service.list("other-workspace")) == 0
    assert service.audit("ws-1")[0].action == "create"


def test_candidate_references_must_be_valid():
    invalid = candidate().model_copy(update={"trigger_signal_ids": ["missing"]})
    with pytest.raises(ValidationError):
        SupervisorCreate(
            workspace_id="ws",
            source_key="source",
            target_system="runtime",
            health_signals=[signal()],
            recovery_candidates=[invalid],
            monitoring_evidence_refs=["evidence"],
        )
