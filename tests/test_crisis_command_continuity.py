import pytest
from pydantic import ValidationError

from backend.app.modules.crisis_command_continuity.models import (
    ContinuityAction,
    CrisisActionRequest,
    CrisisCreate,
    CrisisIncident,
    CrisisState,
    IncidentSeverity,
    RiskDecision,
)
from backend.app.modules.crisis_command_continuity.service import CrisisGovernanceError, CrisisGovernanceService


def payload(workspace: str = "ws") -> CrisisCreate:
    return CrisisCreate(
        workspace_id=workspace,
        source_key="crisis-1",
        enterprise_risk_record_id="risk-1",
        crisis_name="primary-continuity-event",
        incidents=[
            CrisisIncident(
                incident_id="i1",
                domain="execution",
                owner="operations",
                severity=IncidentSeverity.HIGH,
                business_impact=20,
                maximum_tolerable_impact=50,
                recovery_time_objective_minutes=60,
                elapsed_minutes=15,
                evidence_refs=["incident-evidence"],
            )
        ],
        continuity_actions=[
            ContinuityAction(
                action_id="a1",
                title="Fail over runtime",
                owner="operations",
                priority=1,
                confidence=0.95,
                evidence_refs=["action-evidence"],
            )
        ],
        maximum_open_incidents=1,
        maximum_critical_incidents=0,
        maximum_aggregate_impact=50,
        required_healthy_cycles=2,
        crisis_evidence_refs=["crisis-evidence"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, CrisisActionRequest(action=action, actor="tester", **kwargs))


def test_full_crisis_lifecycle():
    service = CrisisGovernanceService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "assess")
    act(service, record, "prepare-command-plan")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval")
    act(service, record, "activate", receipt_id="activation", evidence_refs=["activated"])
    for index in range(2):
        act(
            service,
            record,
            "record-cycle",
            receipt_id=f"cycle-{index}",
            cycle_healthy=True,
            observed_open_incidents=0,
            observed_critical_incidents=0,
            observed_aggregate_impact=0,
        )
    act(service, record, "start-recovery")
    act(service, record, "resolve", receipt_id="resolution", evidence_refs=["resolved"])
    assert record.state == CrisisState.RESOLVED


def test_critical_incident_escalates():
    service = CrisisGovernanceService()
    data = payload().model_copy(
        update={
            "source_key": "critical",
            "incidents": [payload().incidents[0].model_copy(update={"severity": IncidentSeverity.CRITICAL})],
        }
    )
    record = service.create(data)
    act(service, record, "prepare-evidence")
    act(service, record, "assess")
    assert record.state == CrisisState.ESCALATED


def test_risk_block_replay_and_isolation():
    service = CrisisGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == CrisisState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    for action in ["prepare-evidence", "assess", "prepare-command-plan", "request-review"]:
        act(service, record, action)
    act(service, record, "approve", approval_token="unique")
    with pytest.raises(CrisisGovernanceError):
        other = service.create(payload("other").model_copy(update={"source_key": "other"}))
        other.state = CrisisState.REVIEW_REQUIRED
        act(service, other, "approve", approval_token="unique")
    with pytest.raises(CrisisGovernanceError):
        service.get(record.record_id, "other")


def test_duplicate_incidents_rejected():
    incident = payload().incidents[0]
    with pytest.raises(ValidationError):
        CrisisCreate(**payload().model_dump() | {"incidents": [incident.model_dump(), incident.model_dump()]})
