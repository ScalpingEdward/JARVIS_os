import pytest
from pydantic import ValidationError

from backend.app.modules.resilience_engineering.models import (
    ResilienceActionRequest,
    ResilienceCreate,
    ResilienceControl,
    ResilienceScenario,
    ResilienceState,
    RiskDecision,
    TestStatus,
)
from backend.app.modules.resilience_engineering.service import ResilienceGovernanceError, ResilienceGovernanceService


def payload(workspace: str = "alpha", source: str = "src-1", status: TestStatus = TestStatus.PASSED) -> ResilienceCreate:
    return ResilienceCreate(
        workspace_id=workspace,
        source_key=source,
        crisis_record_id="crisis-1",
        program_name="Core continuity validation",
        scenarios=[
            ResilienceScenario(
                scenario_id="scenario-1",
                domain="execution",
                owner="sre",
                status=status,
                target_recovery_minutes=30,
                observed_recovery_minutes=20,
                target_recovery_point_minutes=5,
                observed_recovery_point_minutes=2,
                service_availability=0.999,
                evidence_refs=["evidence://scenario"],
            )
        ],
        controls=[
            ResilienceControl(
                control_id="control-1",
                title="Broker failover",
                owner="platform",
                confidence=0.95,
                evidence_refs=["evidence://control"],
            )
        ],
        maximum_failed_scenarios=0,
        maximum_degraded_scenarios=0,
        minimum_service_availability=0.99,
        required_healthy_cycles=2,
        resilience_evidence_refs=["evidence://program"],
    )


def action(name: str, **kwargs) -> ResilienceActionRequest:
    return ResilienceActionRequest(action=name, actor="operator", **kwargs)


def test_full_resilience_lifecycle() -> None:
    service = ResilienceGovernanceService()
    record = service.create(payload())
    for request in [
        action("prepare-evidence"),
        action("design"),
        action("prepare-test-plan"),
        action("request-review"),
        action("approve", approval_token="approval-1"),
        action("execute", receipt_id="execute-1", evidence_refs=["evidence://execution"]),
        action("record-cycle", receipt_id="cycle-1", cycle_healthy=True),
        action("record-cycle", receipt_id="cycle-2", cycle_healthy=True),
        action("verify"),
    ]:
        record = service.act(record.record_id, "alpha", request)
    assert record.state == ResilienceState.VERIFIED
    assert record.consecutive_healthy_cycles == 2
    assert len(service.audit("alpha")) == 10


def test_failed_scenario_escalates_execution() -> None:
    service = ResilienceGovernanceService()
    record = service.create(payload(status=TestStatus.FAILED))
    for request in [
        action("prepare-evidence"),
        action("design"),
        action("prepare-test-plan"),
        action("request-review"),
        action("approve", approval_token="approval-failed"),
        action("execute", receipt_id="execute-failed"),
    ]:
        record = service.act(record.record_id, "alpha", request)
    assert record.state == ResilienceState.ESCALATED
    assert record.failed_scenarios == 1


def test_risk_block_and_replay_protection() -> None:
    service = ResilienceGovernanceService()
    blocked = payload(source="blocked").model_copy(update={"risk_decision": RiskDecision.BLOCK})
    record = service.create(blocked)
    record = service.act(record.record_id, "alpha", action("prepare-evidence"))
    assert record.state == ResilienceState.BLOCKED

    first = service.create(payload(source="first"))
    second = service.create(payload(source="second"))
    for item in (first, second):
        for request in [action("prepare-evidence"), action("design"), action("prepare-test-plan"), action("request-review")]:
            service.act(item.record_id, "alpha", request)
    service.act(first.record_id, "alpha", action("approve", approval_token="shared-token"))
    with pytest.raises(ResilienceGovernanceError, match="replay"):
        service.act(second.record_id, "alpha", action("approve", approval_token="shared-token"))


def test_workspace_isolation_and_duplicate_source() -> None:
    service = ResilienceGovernanceService()
    record = service.create(payload())
    with pytest.raises(ResilienceGovernanceError, match="not found"):
        service.get(record.record_id, "beta")
    with pytest.raises(ResilienceGovernanceError, match="duplicate"):
        service.create(payload())
    assert service.list("beta") == []


def test_duplicate_scenario_validation() -> None:
    data = payload().model_dump()
    data["scenarios"] = data["scenarios"] * 2
    with pytest.raises(ValidationError, match="scenario_id values must be unique"):
        ResilienceCreate(**data)
