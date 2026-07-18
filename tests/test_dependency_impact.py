from uuid import uuid4

import pytest

from app.dependency_impact.models import (
    AnalysisCreate, AnalysisState, Criticality, DependencyCreate, DependencyKind,
    GraphNodeCreate, Mutation, NodeKind,
)
from app.dependency_impact.service import DependencyImpactService


def node(service: DependencyImpactService, key: str, owner: str, criticality: Criticality = Criticality.MEDIUM, workspace: str = "w1"):
    return service.create_node(GraphNodeCreate(
        workspace_id=workspace,
        owner_id=owner,
        node_key=key,
        name=key,
        kind=NodeKind.SERVICE,
        criticality=criticality,
    ))


def test_blast_radius_propagates_and_scores_critical_nodes():
    service = DependencyImpactService()
    api = node(service, "api", "alice")
    risk = node(service, "risk", "bob", Criticality.HIGH)
    broker = node(service, "broker", "carol", Criticality.CRITICAL)
    service.create_dependency(DependencyCreate(workspace_id="w1", requester_id="alice", source_node_id=api.id, target_node_id=risk.id, kind=DependencyKind.HARD, propagation_weight=90))
    service.create_dependency(DependencyCreate(workspace_id="w1", requester_id="bob", source_node_id=risk.id, target_node_id=broker.id, kind=DependencyKind.CONTROL, propagation_weight=80))
    analysis = service.create_analysis(AnalysisCreate(workspace_id="w1", owner_id="alice", source_node_ids=[api.id], scenario="api outage"))
    assert [x.node_key for x in analysis.impacted_nodes] == ["broker", "risk"] or [x.node_key for x in analysis.impacted_nodes] == ["risk", "broker"]
    assert analysis.critical_nodes == 1
    assert analysis.blast_radius_score > 0


def test_workspace_isolation_and_owner_controls():
    service = DependencyImpactService()
    a = node(service, "a", "alice", workspace="w1")
    b = node(service, "b", "bob", workspace="w2")
    with pytest.raises(ValueError, match="workspace"):
        service.create_dependency(DependencyCreate(workspace_id="w1", requester_id="alice", source_node_id=a.id, target_node_id=b.id, kind=DependencyKind.HARD))
    analysis = service.create_analysis(AnalysisCreate(workspace_id="w1", owner_id="alice", source_node_ids=[a.id], scenario="test"))
    assert service.set_analysis_state(analysis.id, "w1", Mutation(requester_id="mallory"), AnalysisState.REVIEWED) is None


def test_safety_boundaries():
    with pytest.raises(ValueError, match="external dependency discovery"):
        GraphNodeCreate(workspace_id="w", owner_id="o", node_key="x", name="x", kind=NodeKind.MODULE, discover_external=True)
    node_id = uuid4()
    with pytest.raises(ValueError, match="self-dependencies"):
        DependencyCreate(workspace_id="w", requester_id="o", source_node_id=node_id, target_node_id=node_id, kind=DependencyKind.HARD)
    with pytest.raises(ValueError, match="never execute"):
        AnalysisCreate(workspace_id="w", owner_id="o", source_node_ids=[node_id], scenario="x", automatic_action=True)
