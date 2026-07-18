import pytest

from app.strategic_execution.models import (
    CapacityWindow,
    ExecutionAnalysisCreate,
    ExecutionRisk,
    ExecutionTask,
    ReadinessState,
)
from app.strategic_execution.service import StrategicExecutionService


@pytest.fixture
def service() -> StrategicExecutionService:
    return StrategicExecutionService()


def _payload(workspace: str = "alpha") -> ExecutionAnalysisCreate:
    return ExecutionAnalysisCreate(
        workspace_id=workspace,
        owner_id="owner-1",
        key="jarvis.execution",
        title="JARVIS execution forecast",
        target_completion_minutes=150,
        tasks=[
            ExecutionTask(
                key="design",
                title="Design",
                duration_minutes=30,
                required_capabilities={"planner": 1},
                risk=ExecutionRisk.LOW,
            ),
            ExecutionTask(
                key="build",
                title="Build",
                duration_minutes=90,
                dependencies=["design"],
                required_capabilities={"python": 2},
                success_probability=0.9,
            ),
            ExecutionTask(
                key="approve",
                title="Approve",
                duration_minutes=15,
                dependencies=["build"],
                human_approval_gate=True,
            ),
        ],
        capacity_windows=[
            CapacityWindow(capability="planner", available_units=1, window_end_offset_minutes=300),
            CapacityWindow(capability="python", available_units=2, window_end_offset_minutes=300),
        ],
    )


def test_critical_path_and_readiness(service: StrategicExecutionService) -> None:
    record = service.create_analysis(_payload())
    assert record.critical_path == ["design", "build", "approve"]
    assert record.total_duration_minutes == 135
    assert record.readiness_state == ReadinessState.CONDITIONAL
    assert any(item.action == "collect-human-approvals" for item in record.recommendations)


def test_capacity_bottleneck_blocks_execution(service: StrategicExecutionService) -> None:
    payload = _payload()
    payload.capacity_windows = [
        CapacityWindow(capability="planner", available_units=1, window_end_offset_minutes=300),
        CapacityWindow(capability="python", available_units=1, window_end_offset_minutes=300),
    ]
    record = service.create_analysis(payload)
    assert record.readiness_state == ReadinessState.BLOCKED
    assert record.bottlenecks[0].capability == "python"
    assert record.success_probability < 0.9


def test_cycle_is_rejected(service: StrategicExecutionService) -> None:
    payload = ExecutionAnalysisCreate(
        workspace_id="alpha",
        owner_id="owner",
        key="cycle",
        title="Cycle",
        tasks=[
            ExecutionTask(key="a", title="A", duration_minutes=1, dependencies=["b"]),
            ExecutionTask(key="b", title="B", duration_minutes=1, dependencies=["a"]),
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        service.create_analysis(payload)


def test_workspace_isolation(service: StrategicExecutionService) -> None:
    record = service.create_analysis(_payload("alpha"))
    assert service.get_analysis("beta", record.id) is None
    assert service.list_analyses("beta") == []


def test_duplicate_key_is_rejected(service: StrategicExecutionService) -> None:
    service.create_analysis(_payload())
    with pytest.raises(ValueError, match="already exists"):
        service.create_analysis(_payload())


def test_automatic_execution_is_rejected() -> None:
    with pytest.raises(ValueError, match="automatic execution"):
        ExecutionAnalysisCreate(
            workspace_id="alpha",
            owner_id="owner",
            key="unsafe",
            title="Unsafe",
            tasks=[ExecutionTask(key="a", title="A", duration_minutes=1)],
            automatic_execution=True,
        )
