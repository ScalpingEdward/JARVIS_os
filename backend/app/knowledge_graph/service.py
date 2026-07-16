from collections import Counter, deque
from uuid import UUID

from .models import (
    EdgeCreate,
    EdgeRecord,
    GraphPath,
    GraphReasonRequest,
    GraphReasonResponse,
    GraphStatus,
    NodeCreate,
    NodeRecord,
)


class KnowledgeGraphService:
    def __init__(self) -> None:
        self._nodes: dict[UUID, NodeRecord] = {}
        self._edges: dict[UUID, EdgeRecord] = {}

    def reset(self) -> None:
        self._nodes.clear()
        self._edges.clear()

    def create_node(self, payload: NodeCreate) -> NodeRecord:
        node = NodeRecord(**payload.model_dump())
        self._nodes[node.id] = node
        return node

    def create_edge(self, payload: EdgeCreate) -> EdgeRecord:
        if payload.source_id not in self._nodes or payload.target_id not in self._nodes:
            raise ValueError("Both edge nodes must exist")
        edge = EdgeRecord(**payload.model_dump())
        self._edges[edge.id] = edge
        return edge

    def get_node(self, node_id: UUID) -> NodeRecord | None:
        return self._nodes.get(node_id)

    def search_nodes(self, query: str, kind: str | None = None) -> list[NodeRecord]:
        needle = query.casefold().strip()
        results: list[NodeRecord] = []
        for node in self._nodes.values():
            if kind and node.kind.value != kind:
                continue
            haystack = " ".join([node.name, *node.aliases, *node.tags]).casefold()
            if needle in haystack:
                results.append(node)
        return results

    def neighbors(self, node_id: UUID, direction: str = "both") -> list[dict]:
        if node_id not in self._nodes:
            return []
        items: list[dict] = []
        for edge in self._edges.values():
            if direction in {"out", "both"} and edge.source_id == node_id:
                items.append({"edge": edge, "node": self._nodes[edge.target_id], "direction": "out"})
            if direction in {"in", "both"} and edge.target_id == node_id:
                items.append({"edge": edge, "node": self._nodes[edge.source_id], "direction": "in"})
        return items

    def paths(self, source_id: UUID, target_id: UUID, max_depth: int = 5) -> list[GraphPath]:
        if source_id not in self._nodes or target_id not in self._nodes:
            return []
        queue = deque([(source_id, [source_id], [], 0.0)])
        found: list[GraphPath] = []
        while queue:
            current, node_ids, edge_ids, weight = queue.popleft()
            if len(edge_ids) >= max_depth:
                continue
            for edge in self._edges.values():
                if edge.source_id != current or edge.target_id in node_ids:
                    continue
                next_nodes = [*node_ids, edge.target_id]
                next_edges = [*edge_ids, edge.id]
                next_weight = weight + (edge.weight * edge.confidence)
                if edge.target_id == target_id:
                    found.append(GraphPath(node_ids=next_nodes, edge_ids=next_edges, total_weight=round(next_weight, 4)))
                else:
                    queue.append((edge.target_id, next_nodes, next_edges, next_weight))
        return sorted(found, key=lambda item: item.total_weight, reverse=True)[:20]

    def similar(self, node_id: UUID, limit: int = 10) -> list[dict]:
        source = self._nodes.get(node_id)
        if source is None:
            return []
        results: list[dict] = []
        source_tags = set(source.tags)
        for node in self._nodes.values():
            if node.id == node_id:
                continue
            overlap = source_tags & set(node.tags)
            score = len(overlap) / max(len(source_tags | set(node.tags)), 1)
            explicit = any(
                edge.kind.value == "similar_to"
                and {edge.source_id, edge.target_id} == {node_id, node.id}
                for edge in self._edges.values()
            )
            if explicit:
                score = max(score, 0.9)
            if score > 0:
                results.append({"node": node, "score": round(score, 4), "shared_tags": sorted(overlap)})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]

    def reason(self, payload: GraphReasonRequest) -> GraphReasonResponse:
        paths: list[GraphPath] = []
        starts = payload.start_node_ids or list(self._nodes)[:5]
        for source_id in starts:
            for target_id in self._nodes:
                if source_id != target_id:
                    paths.extend(self.paths(source_id, target_id, payload.max_depth))
        paths = sorted(paths, key=lambda item: item.total_weight, reverse=True)[:8]
        if not paths:
            return GraphReasonResponse(
                answer="Insufficient connected evidence in the graph.",
                supporting_paths=[],
                confidence=0.0,
                limitations=["No supporting path found", "Reasoning is limited to stored graph evidence"],
            )
        labels: list[str] = []
        for path in paths[:3]:
            labels.append(" -> ".join(self._nodes[node_id].name for node_id in path.node_ids))
        confidence = min(0.95, sum(path.total_weight for path in paths) / max(len(paths), 1) / payload.max_depth)
        return GraphReasonResponse(
            answer=f"Strongest stored relationships for '{payload.question}': " + "; ".join(labels),
            supporting_paths=paths,
            confidence=round(confidence, 4),
            limitations=["This is graph-based inference, not proof", "Only stored sources and relations were considered"],
        )

    def status(self) -> GraphStatus:
        return GraphStatus(
            nodes=len(self._nodes),
            edges=len(self._edges),
            node_kinds=dict(Counter(node.kind.value for node in self._nodes.values())),
            edge_kinds=dict(Counter(edge.kind.value for edge in self._edges.values())),
        )


knowledge_graph_service = KnowledgeGraphService()
