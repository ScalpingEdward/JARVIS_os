from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AnalysisCreate, AnalysisRecord, AnalysisState, Criticality, DependencyCreate,
    DependencyImpactStatus, DependencyRecord, GraphNodeCreate, GraphNodeRecord,
    ImpactedNode, MetricsRecord, Mutation,
)


CRITICALITY_WEIGHT = {
    Criticality.LOW: 25,
    Criticality.MEDIUM: 50,
    Criticality.HIGH: 75,
    Criticality.CRITICAL: 100,
}


class DependencyImpactService:
    def __init__(self) -> None:
        self.nodes: dict[UUID, GraphNodeRecord] = {}
        self.dependencies: dict[UUID, DependencyRecord] = {}
        self.analyses: dict[UUID, AnalysisRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> DependencyImpactStatus:
        return DependencyImpactStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def create_node(self, payload: GraphNodeCreate) -> GraphNodeRecord:
        if any(x.workspace_id == payload.workspace_id and x.node_key == payload.node_key for x in self.nodes.values()):
            raise ValueError("dependency node key already exists")
        item = GraphNodeRecord(**payload.model_dump())
        self.nodes[item.id] = item
        self._audit(item.workspace_id, "node.created", item.owner_id, item.id)
        return item

    def list_nodes(self, workspace_id: str) -> list[GraphNodeRecord]:
        return [x for x in self.nodes.values() if x.workspace_id == workspace_id]

    def get_node(self, node_id: UUID, workspace_id: str) -> GraphNodeRecord | None:
        item = self.nodes.get(node_id)
        return item if item and item.workspace_id == workspace_id else None

    def create_dependency(self, payload: DependencyCreate) -> DependencyRecord:
        source = self.get_node(payload.source_node_id, payload.workspace_id)
        target = self.get_node(payload.target_node_id, payload.workspace_id)
        if source is None or target is None:
            raise ValueError("dependency nodes must belong to the workspace")
        if payload.requester_id not in {source.owner_id, target.owner_id}:
            raise ValueError("requester must own one side of the dependency")
        if any(
            x.workspace_id == payload.workspace_id
            and x.source_node_id == payload.source_node_id
            and x.target_node_id == payload.target_node_id
            and x.kind == payload.kind
            for x in self.dependencies.values()
        ):
            raise ValueError("dependency already exists")
        item = DependencyRecord(**payload.model_dump())
        self.dependencies[item.id] = item
        self._audit(item.workspace_id, "dependency.created", item.requester_id, item.id)
        return item

    def list_dependencies(self, workspace_id: str) -> list[DependencyRecord]:
        return [x for x in self.dependencies.values() if x.workspace_id == workspace_id]

    def create_analysis(self, payload: AnalysisCreate) -> AnalysisRecord:
        sources = [self.get_node(node_id, payload.workspace_id) for node_id in payload.source_node_ids]
        if any(node is None for node in sources):
            raise ValueError("all analysis source nodes must belong to the workspace")
        item = AnalysisRecord(**payload.model_dump())
        impacted: dict[UUID, ImpactedNode] = {}
        queue = deque((node.id, 0, 100, [node.node_key]) for node in sources if node is not None)

        outgoing: dict[UUID, list[DependencyRecord]] = {}
        for dependency in self.list_dependencies(payload.workspace_id):
            outgoing.setdefault(dependency.source_node_id, []).append(dependency)

        visited_best: dict[UUID, int] = {}
        while queue:
            node_id, depth, inherited_score, path = queue.popleft()
            if depth >= payload.max_depth:
                continue
            for dependency in outgoing.get(node_id, []):
                target = self.get_node(dependency.target_node_id, payload.workspace_id)
                if target is None or target.id in payload.source_node_ids:
                    continue
                propagated = round(inherited_score * dependency.propagation_weight / 100)
                score = round((propagated + CRITICALITY_WEIGHT[target.criticality]) / 2)
                next_depth = depth + 1
                if visited_best.get(target.id, -1) >= score:
                    continue
                visited_best[target.id] = score
                next_path = [*path, target.node_key]
                impacted[target.id] = ImpactedNode(
                    node_id=target.id,
                    node_key=target.node_key,
                    name=target.name,
                    kind=target.kind,
                    criticality=target.criticality,
                    depth=next_depth,
                    impact_score=min(score, 100),
                    path=next_path,
                )
                queue.append((target.id, next_depth, min(score, 100), next_path))

        item.impacted_nodes = sorted(impacted.values(), key=lambda x: (-x.impact_score, x.depth, x.node_key))
        item.critical_nodes = sum(x.criticality == Criticality.CRITICAL for x in item.impacted_nodes)
        item.high_nodes = sum(x.criticality == Criticality.HIGH for x in item.impacted_nodes)
        if item.impacted_nodes:
            average = sum(x.impact_score for x in item.impacted_nodes) / len(item.impacted_nodes)
            scale = min(len(item.impacted_nodes) / 10, 1)
            item.blast_radius_score = min(round(average * (0.6 + 0.4 * scale)), 100)
        self.analyses[item.id] = item
        self._audit(item.workspace_id, "analysis.created", item.owner_id, item.id)
        return item

    def list_analyses(self, workspace_id: str, state: AnalysisState | None = None) -> list[AnalysisRecord]:
        return [x for x in self.analyses.values() if x.workspace_id == workspace_id and (state is None or x.state == state)]

    def get_analysis(self, analysis_id: UUID, workspace_id: str) -> AnalysisRecord | None:
        item = self.analyses.get(analysis_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_analysis_state(self, analysis_id: UUID, workspace_id: str, payload: Mutation, target: AnalysisState) -> AnalysisRecord | None:
        item = self.get_analysis(analysis_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        allowed = {
            AnalysisState.DRAFT: {AnalysisState.REVIEWED, AnalysisState.ARCHIVED},
            AnalysisState.REVIEWED: {AnalysisState.APPROVED, AnalysisState.DRAFT, AnalysisState.ARCHIVED},
            AnalysisState.APPROVED: {AnalysisState.ARCHIVED},
            AnalysisState.ARCHIVED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid impact-analysis transition")
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"analysis.{target.value}", payload.requester_id, item.id)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        nodes = self.list_nodes(workspace_id)
        dependencies = self.list_dependencies(workspace_id)
        analyses = self.list_analyses(workspace_id)
        critical_impacts = sum(x.critical_nodes for x in analyses)
        average = round(sum(x.blast_radius_score for x in analyses) / len(analyses), 2) if analyses else 0.0
        return MetricsRecord(
            workspace_id=workspace_id,
            nodes=len(nodes),
            dependencies=len(dependencies),
            analyses=len(analyses),
            critical_impacts=critical_impacts,
            average_blast_radius=average,
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [x for x in self.audit if x["workspace_id"] == workspace_id]


dependency_impact_service = DependencyImpactService()
