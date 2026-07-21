import pytest

from app.modules.executive_kpi_engine.models import (
    ExecutiveKPIConfig,
    ExecutiveKPICreate,
    ExecutiveKPIExecuteRequest,
    ExecutiveKPIState,
    RoadmapMilestoneEvidence,
)
from app.modules.executive_kpi_engine.service import ExecutiveKPIService


def payload(**overrides):
    data = dict(
        workspace_id="alpha",
        source_key="roadmap-1",
        actor_id="operator",
        v21_05_roadmap_approved=True,
        upstream_risk_brain_blocked=False,
        roadmap_record_id="rm-1",
        roadmap_state="issued-to-kpi",
        roadmap_confidence=92,
        strategic_metrics=["revenue growth", "delivery reliability"],
        constraints=["no risk increase", "budget ceiling fixed"],
        milestones=[
            RoadmapMilestoneEvidence(
                milestone_id="m1",
                title="Foundation release",
                owner_role="engineering-lead",
                budget=10000,
                expected_value=30000,
                exit_criteria=["all tests green"],
                dependency_ready=True,
            ),
            RoadmapMilestoneEvidence(
                milestone_id="m2",
                title="Operational rollout",
                owner_role="operations-lead",
                budget=5000,
                expected_value=20000,
                exit_criteria=["SLO verified"],
                dependency_ready=True,
            ),
        ],
        config=ExecutiveKPIConfig(
            warning_threshold_pct=10,
            critical_threshold_pct=25,
            minimum_confidence=70,
            measurement_frequency="weekly",
        ),
    )
    data.update(overrides)
    return ExecutiveKPICreate(**data)


def test_generates_governed_kpi_set():
    service = ExecutiveKPIService()
    record = service.create(payload())
    assert record.state == ExecutiveKPIState.KPI_SET_READY
    assert record.coverage_score >= 80
    assert len(record.indicators) == 6
    assert any(item.key == "portfolio-budget-adherence" for item in record.indicators)


def test_approval_and_issue_require_human_authority():
    service = ExecutiveKPIService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.execute(record.id, "alpha", ExecutiveKPIExecuteRequest(action="approve", actor_id="agent"))

    approved = service.execute(
        record.id,
        "alpha",
        ExecutiveKPIExecuteRequest(action="approve", actor_id="owner", human_approved=True),
    )
    assert approved.state == ExecutiveKPIState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.id,
        "alpha",
        ExecutiveKPIExecuteRequest(
            action="issue-to-risk-analysis",
            actor_id="owner",
            human_approved=True,
            risk_analysis_receipt_id="risk-receipt-1",
        ),
    )
    assert issued.state == ExecutiveKPIState.ISSUED_TO_RISK_ANALYSIS


def test_low_confidence_escalates_to_human_review():
    service = ExecutiveKPIService()
    record = service.create(payload(roadmap_confidence=50))
    assert record.state == ExecutiveKPIState.HUMAN_REVIEW_REQUIRED


def test_missing_v21_05_evidence_fails_closed():
    service = ExecutiveKPIService()
    record = service.create(payload(v21_05_roadmap_approved=False))
    assert record.state == ExecutiveKPIState.EVIDENCE_REQUIRED


def test_risk_brain_block_is_authoritative():
    service = ExecutiveKPIService()
    record = service.create(payload(upstream_risk_brain_blocked=True))
    assert record.state == ExecutiveKPIState.BLOCKED


def test_dependency_blocked_milestone_is_rejected():
    service = ExecutiveKPIService()
    milestones = payload().milestones
    milestones[0] = milestones[0].model_copy(update={"dependency_ready": False})
    record = service.create(payload(milestones=milestones))
    assert record.state == ExecutiveKPIState.BLOCKED


def test_duplicate_source_and_roadmap_replay_are_rejected():
    service = ExecutiveKPIService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
    with pytest.raises(ValueError, match="roadmap record already consumed"):
        service.create(payload(source_key="roadmap-2"))


def test_receipt_replay_and_workspace_isolation():
    service = ExecutiveKPIService()
    first = service.create(payload())
    service.execute(first.id, "alpha", ExecutiveKPIExecuteRequest(action="approve", actor_id="owner", human_approved=True))
    service.execute(
        first.id,
        "alpha",
        ExecutiveKPIExecuteRequest(action="issue-to-risk-analysis", actor_id="owner", human_approved=True, risk_analysis_receipt_id="receipt-x"),
    )

    second = service.create(payload(source_key="roadmap-2", roadmap_record_id="rm-2"))
    service.execute(second.id, "alpha", ExecutiveKPIExecuteRequest(action="approve", actor_id="owner", human_approved=True))
    with pytest.raises(ValueError, match="risk analysis receipt already consumed"):
        service.execute(
            second.id,
            "alpha",
            ExecutiveKPIExecuteRequest(action="issue-to-risk-analysis", actor_id="owner", human_approved=True, risk_analysis_receipt_id="receipt-x"),
        )

    assert service.get(first.id, "other") is None
    assert service.list_records("other") == []
