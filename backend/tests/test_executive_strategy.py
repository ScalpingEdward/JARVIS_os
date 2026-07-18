import pytest

from app.executive_strategy.models import (
    ExecutiveStrategyCreate,
    ResourcePool,
    StrategicInitiative,
    StrategicObjective,
    StrategicRisk,
    StrategyStatus,
    WhatIfRequest,
)
from app.executive_strategy.service import ExecutiveStrategyService


def payload(workspace_id: str = "ws-a") -> ExecutiveStrategyCreate:
    return ExecutiveStrategyCreate(
        workspace_id=workspace_id,
        owner_id="owner",
        title="Growth strategy",
        horizon_days=365,
        objectives=[
            StrategicObjective(objective_key="growth", title="Revenue growth", weight=60, target_value=100, current_value=40),
            StrategicObjective(objective_key="resilience", title="Operational resilience", weight=40, target_value=100, current_value=70),
        ],
        resources=[ResourcePool(resource_key="engineering", capacity=10), ResourcePool(resource_key="capital", capacity=100)],
        initiatives=[
            StrategicInitiative(
                initiative_key="platform",
                title="Platform foundation",
                objective_keys=["growth", "resilience"],
                strategic_value=90,
                confidence=85,
                risk_score=20,
                resource_demand={"engineering": 4, "capital": 40},
                duration_days=30,
                milestone_titles=["Architecture", "Launch"],
            ),
            StrategicInitiative(
                initiative_key="expansion",
                title="Market expansion",
                objective_keys=["growth"],
                dependencies=["platform"],
                strategic_value=85,
                confidence=75,
                risk_score=35,
                resource_demand={"engineering": 5, "capital": 50},
                duration_days=45,
            ),
        ],
        risks=[StrategicRisk(risk_key="delivery", title="Delivery delay", probability=40, impact=70, mitigation="Phase rollout", initiative_keys=["platform"])],
    )


def test_strategy_analysis_builds_portfolio_graph_allocation_and_roadmap() -> None:
    service = ExecutiveStrategyService()
    record = service.create(payload())
    analyzed = service.analyze(record.id, "ws-a", "analyst")
    assert analyzed.status == StrategyStatus.analyzed
    assert analyzed.analysis is not None
    assert analyzed.analysis.dependency_graph["expansion"] == ["platform"]
    assert analyzed.analysis.roadmap[1].start_day == analyzed.analysis.roadmap[0].end_day
    assert analyzed.analysis.resource_allocation["platform"]["engineering"] == 4
    assert analyzed.analysis.milestones
    assert analyzed.analysis.autonomous_actions_enabled is False


def test_what_if_simulation_can_expose_resource_constraints() -> None:
    service = ExecutiveStrategyService()
    record = service.create(payload())
    analyzed = service.analyze(record.id, "ws-a", "analyst", WhatIfRequest(resource_capacity_overrides={"engineering": 3}))
    assert analyzed.analysis is not None
    assert any(not item.feasible for item in analyzed.analysis.initiatives)
    assert analyzed.analysis.scenario_summary.startswith("Scenario evaluated")


def test_cycle_invalid_weights_and_unknown_references_are_rejected() -> None:
    data = payload()
    data.initiatives[0].dependencies = ["expansion"]
    service = ExecutiveStrategyService()
    record = service.create(data)
    with pytest.raises(ValueError):
        service.analyze(record.id, "ws-a", "analyst")

    with pytest.raises(ValueError):
        ExecutiveStrategyCreate(
            workspace_id="ws",
            owner_id="owner",
            title="Invalid",
            objectives=[StrategicObjective(objective_key="a", title="A", weight=90, target_value=1)],
            initiatives=[StrategicInitiative(initiative_key="i", title="I", objective_keys=["missing"])],
        )


def test_workspace_isolation_duplicates_status_and_audit() -> None:
    service = ExecutiveStrategyService()
    record = service.create(payload())
    assert service.get(record.id, "ws-b") is None
    assert service.list_plans("ws-b") == []
    with pytest.raises(ValueError):
        service.create(payload())
    service.analyze(record.id, "ws-a", "analyst")
    status = service.status("ws-a")
    assert status.version == "18.3"
    assert status.plans == 1
    assert status.analyzed_plans == 1
    assert status.autonomous_actions_enabled is False
    assert len(service.audit_records("ws-a")) == 2
    assert service.audit_records("ws-b") == []
