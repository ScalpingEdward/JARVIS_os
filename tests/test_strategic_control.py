import pytest
from pydantic import ValidationError

from backend.app.modules.strategic_control.models import MissionActionRequest, MissionObjective, MissionPriority, MissionState, RiskDecision, StrategicMissionCreate
from backend.app.modules.strategic_control.service import StrategicControlError, StrategicControlService


def payload(workspace: str = "ws") -> StrategicMissionCreate:
    return StrategicMissionCreate(
        workspace_id=workspace,
        source_key="governance-1",
        governance_record_id="gov-1",
        mission_name="stabilize autonomous operations",
        priority=MissionPriority.HIGH,
        objectives=[MissionObjective(objective_id="o1", title="maintain health", target_metric="healthy_cycles", target_value=3, evidence_refs=["ev-1"])],
        strategic_evidence_refs=["gov-evidence"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, MissionActionRequest(action=action, actor="tester", **kwargs))


def test_full_mission_lifecycle():
    service = StrategicControlService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "align")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="a1")
    act(service, record, "activate", receipt_id="r1")
    act(service, record, "start", receipt_id="r2")
    for index in range(3):
        act(service, record, "record-cycle", receipt_id=f"c{index}", cycle_successful=True, evidence_refs=[f"e{index}"])
    act(service, record, "achieve", receipt_id="done")
    assert record.state == MissionState.ACHIEVED


def test_risk_escalation_and_block():
    service = StrategicControlService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == MissionState.BLOCKED
    risky = service.create(payload("risk").model_copy(update={"source_key": "risk", "aggregate_risk": 0.9}))
    act(service, risky, "prepare-evidence")
    act(service, risky, "align")
    assert risky.state == MissionState.ESCALATED


def test_replay_protection():
    service = StrategicControlService()
    record = service.create(payload())
    for action, kwargs in [("prepare-evidence", {}), ("align", {}), ("request-review", {}), ("approve", {"approval_token": "a"}), ("activate", {"receipt_id": "r"})]:
        act(service, record, action, **kwargs)
    with pytest.raises(StrategicControlError):
        act(service, record, "start", receipt_id="r")


def test_duplicate_objective_ids_rejected():
    objective = payload().objectives[0]
    with pytest.raises(ValidationError):
        StrategicMissionCreate(**payload().model_dump(exclude={"objectives"}), objectives=[objective, objective])


def test_workspace_isolation():
    service = StrategicControlService()
    record = service.create(payload())
    with pytest.raises(StrategicControlError):
        service.get(record.record_id, "other")
