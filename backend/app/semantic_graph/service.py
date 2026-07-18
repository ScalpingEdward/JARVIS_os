from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    EntityState,
    GraphEntityCreate,
    GraphEntityRecord,
    GraphPath,
    GraphSearchHit,
    GraphSearchRequest,
    ImpactResult,
    KnowledgeGraphStatus,
    RelationshipCreate,
    RelationshipRecord,
    TraversalRequest,
)


class SemanticGraphService:
    def __init__(self) -> None:
        self.entities: dict[UUID, GraphEntityRecord] = {}
        self.relationships: dict[UUID, RelationshipRecord] = {}
        self.audit_records: list[AuditRecord] = []

    def reset(self) -> None:
        self.entities.clear()
        self.relationships.clear()
        self.audit_records.clear()

    def create_entity(self, payload: GraphEntityCreate) -> GraphEntityRecord:
        duplicate = next(
            (entity for entity in self.entities.values() if entity.workspace_id == payload.workspace_id and entity.key == payload.key),
            None,
        )
        if duplicate:
            raise ValueError("entity key already exists in workspace")
        record = GraphEntityRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        self.entities[record.id] = record
        self._audit(payload.workspace_id, payload.owner_id, "entity.created", "entity", record.id, {"key": record.key})
        return record

    def create_relationship(self, payload: RelationshipCreate) -> RelationshipRecord:
        source = self.entities.get(payload.source_entity_id)
        target = self.entities.get(payload.target_entity_id)
        if source is None or target is None:
            raise ValueError("source and target entities must exist")
        if source.workspace_id != payload.workspace_id or target.workspace_id != payload.workspace_id:
            raise ValueError("cross-workspace relationships are forbidden")
        duplicate = next(
            (
                rel
                for rel in self.relationships.values()
                if rel.workspace_id == payload.workspace_id
                and rel.source_entity_id == payload.source_entity_id
                and rel.target_entity_id == payload.target_entity_id
                and rel.relationship_type == payload.relationship_type
            ),
            None,
        )
        if duplicate:
            raise ValueError("relationship already exists")
        record = RelationshipRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        self.relationships[record.id] = record
        self._audit(payload.workspace_id, payload.owner_id, "relationship.created", "relationship", record.id, {})
        return record

    def list_entities(self, workspace_id: str, include_archived: bool = False) -> list[GraphEntityRecord]:
        return sorted(
            [
                entity
                for entity in self.entities.values()
                if entity.workspace_id == workspace_id and (include_archived or entity.state != EntityState.ARCHIVED)
            ],
            key=lambda item: (item.entity_type.value, item.key),
        )

    def get_entity(self, workspace_id: str, entity_id: UUID) -> GraphEntityRecord | None:
        entity = self.entities.get(entity_id)
        return entity if entity and entity.workspace_id == workspace_id else None

    def search(self, payload: GraphSearchRequest) -> list[GraphSearchHit]:
        terms = [term.lower() for term in payload.query.split() if term.strip()]
        hits: list[GraphSearchHit] = []
        for entity in self.list_entities(payload.workspace_id, payload.include_archived):
            if payload.entity_types and entity.entity_type not in payload.entity_types:
                continue
            if entity.confidence < payload.minimum_confidence:
                continue
            fields = {
                "name": entity.name.lower(),
                "key": entity.key.lower(),
                "description": entity.description.lower(),
                "aliases": " ".join(entity.aliases).lower(),
                "tags": " ".join(entity.tags).lower(),
            }
            matched = [field for field, value in fields.items() if any(term in value for term in terms)]
            if not matched:
                continue
            score = min(1.0, (len(matched) / 5.0) + (0.25 * entity.confidence))
            hits.append(GraphSearchHit(entity=entity, score=round(score, 4), matched_fields=matched))
        return sorted(hits, key=lambda hit: (-hit.score, hit.entity.key))[: payload.limit]

    def traverse(self, payload: TraversalRequest) -> list[GraphPath]:
        start = self.get_entity(payload.workspace_id, payload.start_entity_id)
        if start is None:
            raise ValueError("start entity not found")
        queue: deque[tuple[UUID, list[UUID], list[UUID], float]] = deque([(start.id, [start.id], [], 1.0)])
        paths: list[GraphPath] = []
        visited_depth: dict[UUID, int] = {start.id: 0}
        while queue:
            current_id, entity_path, relationship_path, confidence = queue.popleft()
            depth = len(relationship_path)
            if depth >= payload.max_depth:
                continue
            for relationship, neighbor_id in self._neighbors(payload.workspace_id, current_id, payload):
                if neighbor_id in entity_path:
                    continue
                next_depth = depth + 1
                if visited_depth.get(neighbor_id, next_depth) < next_depth:
                    continue
                visited_depth[neighbor_id] = next_depth
                next_entities = [*entity_path, neighbor_id]
                next_relationships = [*relationship_path, relationship.id]
                next_confidence = confidence * relationship.confidence
                paths.append(
                    GraphPath(
                        entity_ids=next_entities,
                        relationship_ids=next_relationships,
                        depth=next_depth,
                        confidence=round(next_confidence, 4),
                    )
                )
                queue.append((neighbor_id, next_entities, next_relationships, next_confidence))
        return sorted(paths, key=lambda path: (path.depth, -path.confidence, str(path.entity_ids[-1])))

    def impact(self, payload: TraversalRequest) -> ImpactResult:
        root = self.get_entity(payload.workspace_id, payload.start_entity_id)
        if root is None:
            raise ValueError("root entity not found")
        paths = self.traverse(payload)
        affected_ids: list[UUID] = []
        for path in paths:
            target_id = path.entity_ids[-1]
            if target_id not in affected_ids:
                affected_ids.append(target_id)
        affected = [self.entities[entity_id] for entity_id in affected_ids]
        return ImpactResult(
            root_entity=root,
            affected_entities=affected,
            paths=paths,
            impact_count=len(affected),
            max_depth=max((path.depth for path in paths), default=0),
        )

    def status(self, workspace_id: str) -> KnowledgeGraphStatus:
        entities = [entity for entity in self.entities.values() if entity.workspace_id == workspace_id]
        relationships = [rel for rel in self.relationships.values() if rel.workspace_id == workspace_id]
        return KnowledgeGraphStatus(
            entities=len(entities),
            relationships=len(relationships),
            active_entities=sum(entity.state == EntityState.ACTIVE for entity in entities),
            archived_entities=sum(entity.state == EntityState.ARCHIVED for entity in entities),
            entity_types=len({entity.entity_type for entity in entities}),
            relationship_types=len({rel.relationship_type for rel in relationships}),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self.audit_records if record.workspace_id == workspace_id]

    def _neighbors(self, workspace_id: str, entity_id: UUID, payload: TraversalRequest):
        for relationship in self.relationships.values():
            if relationship.workspace_id != workspace_id:
                continue
            if payload.relationship_types and relationship.relationship_type not in payload.relationship_types:
                continue
            if payload.direction in {"outgoing", "both"} and relationship.source_entity_id == entity_id:
                yield relationship, relationship.target_entity_id
            if payload.direction in {"incoming", "both"} and relationship.target_entity_id == entity_id:
                yield relationship, relationship.source_entity_id
            if relationship.bidirectional and relationship.target_entity_id == entity_id:
                yield relationship, relationship.source_entity_id

    def _audit(self, workspace_id: str, actor_id: str, action: str, target_type: str, target_id: UUID, details: dict) -> None:
        self.audit_records.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                created_at=datetime.now(timezone.utc),
            )
        )


semantic_graph_service = SemanticGraphService()
