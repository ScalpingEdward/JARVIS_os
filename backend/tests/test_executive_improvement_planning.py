import pytest

from app.executive_improvement_planning.models import (
    ApprovedImprovementEvidence,
    ImprovementPlanningCreate,
    ImprovementPlanningExecuteRequest,
    ImprovementPlanningState,
)
from app.executive_improvement_planning.service import ImprovementPlanningService


def payload(**overrides):
    data = dict(
        workspace_id="workspace-a",
        source_key="incident-learning-1",
        actor_id="operator-1",
        v20_08_improvement_approved=True,
        upstream_risk_brain_blocked=False,
        business_impact=85,
        technical_complexity=40,
        target_sprint="sprint-21",
        evidence=ApprovedImprovementEvidence(
            incident_learning_id="learning-1",
            incident_learning_state="approved",
            improvement_actions=["add stale-feed detection", "add bounded service restart"],
            recurrence_risk_score=75,
            incident_severity="high",
            incident_count=4,
            estimated_outage_cost=15000,
            requires_code_change=True,
            dependencies=["observability"],
        ),
    )
    data.update(overrides)
    return ImprovementPlanningCreate(**data)


def test_prioritizes_approved_improvement():
    service = ImprovementPlanningService()
    record = service.create(payload())
    assert record.state == ImprovementPlanningState.PRIORITIZED
    assert record.aggregate_priority_score >= 60
    assert len(record.backlog_items) == 2
    assert all(item.defensive_only for item in record.backlog_items)


def test_releases_only_with_human_approval():
    service = ImprovementPlanningService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(
            record.id,
            "workspace-a",
            ImprovementPlanningExecuteRequest(action="release-to-v20.01", actor_id="operator-1"),
        )
    released = service.execute(
        record.id,
        "workspace-a",
        ImprovementPlanningExecuteRequest(
            action="release-to-v20.01", actor_id="operator-1", human_approved=True
        ),
    )
    assert released.state == ImprovementPlanningState.READY_FOR_V20_01


def test_requires_approved_v20_08_evidence():
    service = ImprovementPlanningService()
    record = service.create(payload(v20_08_improvement_approved=False))
    assert record.state == ImprovementPlanningState.EVIDENCE_REQUIRED


def test_risk_brain_blocks_fail_closed():
    service = ImprovementPlanningService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == ImprovementPlanningState.BLOCKED


def test_deduplicates_identical_actions():
    service = ImprovementPlanningService()
    evidence = payload().evidence.model_copy(
        update={"improvement_actions": ["add health guard", "add health guard"]}
    )
    record = service.create(payload(evidence=evidence))
    assert len(record.backlog_items) == 1


def test_duplicate_source_key_is_rejected_per_workspace():
    service = ImprovementPlanningService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())


def test_workspace_isolation():
    service = ImprovementPlanningService()
    record = service.create(payload())
    assert service.get(record.id, "workspace-b") is None
    assert service.list_records("workspace-b") == []


def test_scheduling_requires_target_sprint():
    service = ImprovementPlanningService()
    record = service.create(payload(target_sprint=None))
    with pytest.raises(ValueError, match="target_sprint required"):
        service.execute(
            record.id,
            "workspace-a",
            ImprovementPlanningExecuteRequest(
                action="schedule", actor_id="operator-1", human_approved=True
            ),
        )
