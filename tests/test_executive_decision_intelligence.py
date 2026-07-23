import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_52_executive_decision_intelligence.models import (
    ExecutiveActionRequest,
    ExecutiveDecisionCreate,
    ExecutiveOption,
    ExecutiveState,
    ObjectiveStatus,
    RiskDecision,
    StrategicObjective,
)
from backend.app.phoenix.v21_52_executive_decision_intelligence.service import (
    ExecutiveDecisionService,
    ExecutiveGovernanceError,
)


def payload(workspace_id: str = "ws-1", source_key: str = "decision-1") -> ExecutiveDecisionCreate:
    return ExecutiveDecisionCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        maturity_record_id="maturity-1",
        decision_name="Capital allocation decision",
        objectives=[
            StrategicObjective(
                objective_id="growth",
                title="Risk-adjusted growth",
                owner="board",
                weight=0.6,
                current_score=0.9,
                minimum_acceptable_score=0.7,
                status=ObjectiveStatus.ON_TRACK,
                evidence_refs=["evidence:growth"],
            ),
            StrategicObjective(
                objective_id="resilience",
                title="Operational resilience",
                owner="risk",
                weight=0.4,
                current_score=0.85,
                minimum_acceptable_score=0.7,
                status=ObjectiveStatus.ON_TRACK,
                evidence_refs=["evidence:resilience"],
            ),
        ],
        options=[
            ExecutiveOption(
                option_id="option-a",
                title="Controlled expansion",
                owner="executive-board",
                expected_business_impact=0.8,
                expected_risk_impact=0.2,
                confidence=0.95,
                evidence_refs=["evidence:a"],
            ),
            ExecutiveOption(
                option_id="option-b",
                title="Hold current allocation",
                owner="executive-board",
                expected_business_impact=0.3,
                expected_risk_impact=0.05,
                confidence=0.9,
                evidence_refs=["evidence:b"],
            ),
        ],
        selected_option_id="option-a",
        decision_evidence_refs=["evidence:board-pack"],
    )


def act(service: ExecutiveDecisionService, record_id: str, action: str, **kwargs):
    return service.act(
        record_id,
        "ws-1",
        ExecutiveActionRequest(action=action, actor="tester", **kwargs),
    )


def test_full_lifecycle() -> None:
    service = ExecutiveDecisionService()
    record = service.create(payload())
    assert record.state == ExecutiveState.DRAFT
    assert act(service, record.record_id, "prepare-evidence").state == ExecutiveState.EVIDENCE_READY
    assert act(service, record.record_id, "analyze").state == ExecutiveState.ANALYZED
    assert act(service, record.record_id, "prepare-decision").state == ExecutiveState.DECISION_READY
    assert act(service, record.record_id, "request-review").state == ExecutiveState.REVIEW_REQUIRED
    assert act(service, record.record_id, "approve", approval_token="approval-1").state == ExecutiveState.APPROVED
    assert act(service, record.record_id, "activate", receipt_id="receipt-1", evidence_refs=["activation:1"]).state == ExecutiveState.ACTIVATED
    for _ in range(3):
        monitored = act(
            service,
            record.record_id,
            "record-cycle",
            cycle_healthy=True,
            observed_weighted_objective_score=0.9,
            observed_breached_objectives=0,
            observed_at_risk_objectives=0,
        )
    assert monitored.state == ExecutiveState.MONITORING
    assert act(service, record.record_id, "verify").state == ExecutiveState.VERIFIED
    assert act(service, record.record_id, "archive").state == ExecutiveState.ARCHIVED


def test_objective_breach_escalates() -> None:
    service = ExecutiveDecisionService()
    data = payload()
    data.objectives[0].status = ObjectiveStatus.BREACHED
    record = service.create(data)
    act(service, record.record_id, "prepare-evidence")
    assert act(service, record.record_id, "analyze").state == ExecutiveState.ESCALATED


def test_risk_brain_block_is_authoritative() -> None:
    service = ExecutiveDecisionService()
    data = payload()
    data.risk_decision = RiskDecision.BLOCK
    record = service.create(data)
    assert act(service, record.record_id, "prepare-evidence").state == ExecutiveState.BLOCKED


def test_replay_protection() -> None:
    service = ExecutiveDecisionService()
    first = service.create(payload(source_key="first"))
    for action in ("prepare-evidence", "analyze", "prepare-decision", "request-review"):
        act(service, first.record_id, action)
    act(service, first.record_id, "approve", approval_token="shared-token")

    second = service.create(payload(source_key="second"))
    for action in ("prepare-evidence", "analyze", "prepare-decision", "request-review"):
        act(service, second.record_id, action)
    with pytest.raises(ExecutiveGovernanceError, match="replay"):
        act(service, second.record_id, "approve", approval_token="shared-token")


def test_workspace_isolation_and_duplicate_source_key() -> None:
    service = ExecutiveDecisionService()
    record = service.create(payload())
    with pytest.raises(ExecutiveGovernanceError):
        service.get(record.record_id, "ws-2")
    with pytest.raises(ExecutiveGovernanceError, match="duplicate"):
        service.create(payload())


def test_validation_rejects_unknown_selected_option_and_bad_weights() -> None:
    with pytest.raises(ValidationError):
        ExecutiveDecisionCreate(
            **{
                **payload().model_dump(),
                "selected_option_id": "unknown",
            }
        )
    data = payload().model_dump()
    data["objectives"][0]["weight"] = 0.5
    with pytest.raises(ValidationError):
        ExecutiveDecisionCreate(**data)
