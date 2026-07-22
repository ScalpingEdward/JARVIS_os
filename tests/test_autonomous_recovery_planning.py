import pytest
from pydantic import ValidationError

from backend.app.modules.autonomous_recovery_planning.models import (
    RecoveryActionRequest,
    RecoveryPlanCreate,
    RecoveryState,
    RecoveryStep,
    RecoveryStrategy,
    RiskDecision,
)
from backend.app.modules.autonomous_recovery_planning.service import (
    AutonomousRecoveryPlanningError,
    AutonomousRecoveryPlanningService,
)


def payload(source_key: str = "source-1") -> RecoveryPlanCreate:
    return RecoveryPlanCreate(
        workspace_id="workspace-a",
        source_key=source_key,
        assurance_assessment_id="assurance-33",
        trust_assessment_id="trust-32",
        rollback_assessment_id="rollback-31",
        steps=[
            RecoveryStep(
                step_id="observe",
                strategy=RecoveryStrategy.OBSERVE,
                title="Capture runtime baseline",
                target="runtime-1",
                priority=100,
                success_criteria=["baseline captured"],
                max_attempts=1,
                evidence_refs=["evidence-observe"],
            ),
            RecoveryStep(
                step_id="restart",
                strategy=RecoveryStrategy.RESTART,
                title="Restart degraded runtime",
                target="runtime-1",
                priority=80,
                depends_on=["observe"],
                success_criteria=["runtime healthy"],
                failure_criteria=["restart timeout"],
                max_attempts=2,
                cooldown_seconds=30,
                evidence_refs=["evidence-restart"],
            ),
        ],
        assurance_evidence_refs=["assurance-evidence"],
        runtime_evidence_refs=["runtime-evidence"],
    )


def action(name: str, **kwargs) -> RecoveryActionRequest:
    return RecoveryActionRequest(action=name, actor="operator", **kwargs)


def test_full_recovery_lifecycle() -> None:
    service = AutonomousRecoveryPlanningService()
    record = service.create(payload())
    record = service.act(record.record_id, "workspace-a", action("plan"))
    assert record.state == RecoveryState.PLANNED
    record = service.act(record.record_id, "workspace-a", action("request-review"))
    record = service.act(record.record_id, "workspace-a", action("approve", approval_token="approval-1"))
    record = service.act(record.record_id, "workspace-a", action("queue", receipt_id="queue-1"))
    record = service.act(record.record_id, "workspace-a", action("start", receipt_id="start-1"))
    record = service.act(record.record_id, "workspace-a", action("complete-step", step_id="observe", attempt=1, receipt_id="observe-1", execution_evidence_refs=["observe-result"]))
    record = service.act(record.record_id, "workspace-a", action("complete-step", step_id="restart", attempt=1, receipt_id="restart-1", execution_evidence_refs=["restart-result"]))
    record = service.act(record.record_id, "workspace-a", action("verify", receipt_id="verify-1", verification_evidence_refs=["healthy-runtime"]))
    assert record.state == RecoveryState.VERIFIED
    assert len(service.audit("workspace-a")) == 9


def test_dependencies_are_enforced() -> None:
    service = AutonomousRecoveryPlanningService()
    record = service.create(payload())
    for request in (
        action("plan"),
        action("request-review"),
        action("approve", approval_token="approval-2"),
        action("queue", receipt_id="queue-2"),
        action("start", receipt_id="start-2"),
    ):
        record = service.act(record.record_id, "workspace-a", request)
    with pytest.raises(AutonomousRecoveryPlanningError, match="dependencies"):
        service.act(record.record_id, "workspace-a", action("complete-step", step_id="restart", attempt=1, receipt_id="restart-early", execution_evidence_refs=["result"]))


def test_risk_block_is_authoritative() -> None:
    service = AutonomousRecoveryPlanningService()
    blocked = payload().model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK})
    record = service.create(blocked)
    with pytest.raises(AutonomousRecoveryPlanningError, match="hard block"):
        service.act(record.record_id, "workspace-a", action("plan"))


def test_replay_and_workspace_isolation() -> None:
    service = AutonomousRecoveryPlanningService()
    first = service.create(payload("one"))
    second = service.create(payload("two"))
    for record in (first, second):
        service.act(record.record_id, "workspace-a", action("plan"))
        service.act(record.record_id, "workspace-a", action("request-review"))
    service.act(first.record_id, "workspace-a", action("approve", approval_token="same-token"))
    with pytest.raises(AutonomousRecoveryPlanningError, match="replay"):
        service.act(second.record_id, "workspace-a", action("approve", approval_token="same-token"))
    with pytest.raises(AutonomousRecoveryPlanningError, match="not found"):
        service.get(first.record_id, "workspace-b")


def test_dependency_graph_validation() -> None:
    with pytest.raises(ValidationError, match="known recovery steps"):
        RecoveryPlanCreate(
            **payload().model_dump(exclude={"steps"}),
            steps=[RecoveryStep(step_id="x", strategy=RecoveryStrategy.RESTART, title="x", target="r", priority=1, depends_on=["missing"], success_criteria=["ok"], evidence_refs=["e"])],
        )
    with pytest.raises(ValidationError, match="acyclic"):
        RecoveryPlanCreate(
            **payload().model_dump(exclude={"steps"}),
            steps=[
                RecoveryStep(step_id="a", strategy=RecoveryStrategy.OBSERVE, title="a", target="r", priority=2, depends_on=["b"], success_criteria=["ok"], evidence_refs=["e"]),
                RecoveryStep(step_id="b", strategy=RecoveryStrategy.RESTART, title="b", target="r", priority=1, depends_on=["a"], success_criteria=["ok"], evidence_refs=["e"]),
            ],
        )
