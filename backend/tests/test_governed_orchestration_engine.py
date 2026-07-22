import pytest

from app.modules.governed_orchestration_engine.models import (
    OrchestrationAction,
    OrchestrationCommand,
    OrchestrationCreate,
    OrchestrationState,
    WorkflowStep,
)
from app.modules.governed_orchestration_engine.service import (
    GovernedOrchestrationService,
    OrchestrationError,
)


def payload(**overrides):
    data = {
        "workspace_id": "ws-1",
        "source_key": "source-1",
        "strategy_policy_record_id": "policy-1",
        "workflow_name": "approved-trade-flow",
        "steps": [
            WorkflowStep(step_id="validate", module="risk", action="validate"),
            WorkflowStep(step_id="prepare", module="execution", action="prepare", depends_on=["validate"]),
            WorkflowStep(step_id="issue", module="boundary", action="issue", depends_on=["prepare"], requires_human_approval=True),
        ],
        "max_parallel_steps": 2,
        "upstream_evidence_verified": True,
        "active_policy_verified": True,
        "risk_brain_blocked": False,
    }
    data.update(overrides)
    return OrchestrationCreate(**data)


def test_builds_ordered_plan_and_requires_human_review():
    service = GovernedOrchestrationService()
    record = service.create(payload())

    assert record.state == OrchestrationState.HUMAN_REVIEW_REQUIRED
    assert record.plan is not None
    assert record.plan.ordered_step_ids == ["validate", "prepare", "issue"]
    assert record.plan.approval_required_steps == ["issue"]


def test_evidence_and_risk_brain_fail_closed():
    service = GovernedOrchestrationService()
    missing = service.create(payload(source_key="missing", upstream_evidence_verified=False))
    blocked = service.create(payload(source_key="blocked", risk_brain_blocked=True))

    assert missing.state == OrchestrationState.EVIDENCE_REQUIRED
    assert blocked.state == OrchestrationState.BLOCKED


def test_approval_dispatch_completion_and_replay_protection():
    service = GovernedOrchestrationService()
    record = service.create(payload())

    approved = service.act(
        "ws-1",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.APPROVE, actor="human", approval_token="approve-1"),
    )
    dispatched = service.act(
        "ws-1",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.DISPATCH, actor="system", dispatch_receipt="dispatch-1"),
    )
    completed = service.act(
        "ws-1",
        record.id,
        OrchestrationAction(command=OrchestrationCommand.COMPLETE, actor="system", completion_receipt="complete-1"),
    )

    assert approved.state == OrchestrationState.APPROVED
    assert dispatched.state == OrchestrationState.DISPATCHED
    assert completed.state == OrchestrationState.COMPLETED

    second = service.create(payload(source_key="source-2"))
    with pytest.raises(OrchestrationError, match="replay"):
        service.act(
            "ws-1",
            second.id,
            OrchestrationAction(command=OrchestrationCommand.APPROVE, actor="human", approval_token="approve-1"),
        )


def test_rejects_cycles_unknown_dependencies_duplicates_and_cross_workspace_access():
    service = GovernedOrchestrationService()

    with pytest.raises(OrchestrationError, match="cycle"):
        service.create(
            payload(
                source_key="cycle",
                steps=[
                    WorkflowStep(step_id="a", module="m", action="a", depends_on=["b"]),
                    WorkflowStep(step_id="b", module="m", action="b", depends_on=["a"]),
                ],
            )
        )

    with pytest.raises(OrchestrationError, match="unknown dependency"):
        service.create(
            payload(
                source_key="unknown",
                steps=[WorkflowStep(step_id="a", module="m", action="a", depends_on=["missing"])],
            )
        )

    record = service.create(payload(source_key="isolation"))
    with pytest.raises(OrchestrationError, match="record not found"):
        service.get("ws-2", record.id)

    with pytest.raises(OrchestrationError, match="duplicate source_key"):
        service.create(payload(source_key="isolation"))
