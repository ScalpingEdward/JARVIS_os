import pytest

from app.service_registry.models import (
    DependencyCreate, HealthState, HealthUpdate, ImpactRequest, Mutation,
    ServiceCreate, ServiceState,
)
from app.service_registry.service import ServiceRegistryService


def add(service: ServiceRegistryService, key: str, workspace: str = "w1"):
    return service.create_service(ServiceCreate(workspace_id=workspace, owner_id="owner", service_key=key, name=key, version="1.2.0", api_routes=[f"/v1/{key}"], produces_events=[f"{key}.updated"]))


def test_registry_dependency_graph_and_impact():
    registry = ServiceRegistryService()
    core = add(registry, "core")
    api = add(registry, "api")
    ui = add(registry, "ui")
    registry.set_service_state(core.id, "w1", Mutation(requester_id="owner"), ServiceState.ACTIVE)
    registry.create_dependency(DependencyCreate(workspace_id="w1", owner_id="owner", source_service_id=api.id, target_service_id=core.id, minimum_version="1.0.0"))
    registry.create_dependency(DependencyCreate(workspace_id="w1", owner_id="owner", source_service_id=ui.id, target_service_id=api.id))
    graph = registry.graph("w1")
    assert len(graph.nodes) == 3
    assert graph.cycles == []
    impact = registry.impact(ImpactRequest(workspace_id="w1", service_id=core.id, changed_routes=["/v1/core"]))
    assert set(impact.affected_service_ids) == {api.id, ui.id}
    assert impact.risk_score > 0


def test_cycle_duplicate_health_and_workspace_isolation():
    registry = ServiceRegistryService()
    a = add(registry, "a")
    b = add(registry, "b")
    registry.create_dependency(DependencyCreate(workspace_id="w1", owner_id="owner", source_service_id=a.id, target_service_id=b.id))
    with pytest.raises(ValueError):
        registry.create_dependency(DependencyCreate(workspace_id="w1", owner_id="owner", source_service_id=b.id, target_service_id=a.id))
    with pytest.raises(ValueError):
        registry.create_dependency(DependencyCreate(workspace_id="w1", owner_id="owner", source_service_id=a.id, target_service_id=b.id))
    assert registry.update_health(a.id, "w2", HealthUpdate(requester_id="owner", state=HealthState.HEALTHY)) is None
    assert registry.update_health(a.id, "w1", HealthUpdate(requester_id="owner", state=HealthState.HEALTHY)).health == HealthState.HEALTHY


def test_safety_blocks_automation_and_execution():
    with pytest.raises(ValueError):
        ServiceCreate(workspace_id="w1", owner_id="owner", service_key="x", name="x", version="1.0.0", automatic_activation=True)
    with pytest.raises(ValueError):
        ServiceCreate(workspace_id="w1", owner_id="owner", service_key="x", name="x", version="1.0.0", external_discovery=True)
    registry = ServiceRegistryService()
    item = add(registry, "x")
    with pytest.raises(ValueError):
        ImpactRequest(workspace_id="w1", service_id=item.id, execute_changes=True)
