from datetime import datetime, timezone
from uuid import UUID

from .models import (
    EntityState,
    RelationCreate,
    RelationKind,
    WorldEntity,
    WorldEntityCreate,
    WorldEvent,
    WorldEventCreate,
    WorldRelation,
    WorldSnapshot,
)


class WorldModelService:
    def __init__(self) -> None:
        self._entities: dict[UUID, WorldEntity] = {}
        self._relations: dict[UUID, WorldRelation] = {}
        self._events: list[WorldEvent] = []

    def reset(self) -> None:
        self._entities.clear()
        self._relations.clear()
        self._events.clear()

    def upsert_entity(self, payload: WorldEntityCreate) -> WorldEntity:
        for entity in self._entities.values():
            if entity.kind == payload.kind and entity.external_id == payload.external_id:
                entity.name = payload.name
                entity.state = payload.state
                entity.priority = payload.priority
                entity.attributes = payload.attributes
                entity.updated_at = datetime.now(timezone.utc)
                return entity
        entity = WorldEntity(**payload.model_dump())
        self._entities[entity.id] = entity
        return entity

    def list_entities(self, state: EntityState | None = None) -> list[WorldEntity]:
        items = list(self._entities.values())
        return items if state is None else [item for item in items if item.state == state]

    def get_entity(self, entity_id: UUID) -> WorldEntity | None:
        return self._entities.get(entity_id)

    def add_relation(self, payload: RelationCreate) -> WorldRelation:
        if payload.source_id not in self._entities or payload.target_id not in self._entities:
            raise ValueError("Both relation entities must exist")
        relation = WorldRelation(**payload.model_dump())
        self._relations[relation.id] = relation
        return relation

    def list_relations(self, entity_id: UUID | None = None) -> list[WorldRelation]:
        relations = list(self._relations.values())
        if entity_id is None:
            return relations
        return [r for r in relations if r.source_id == entity_id or r.target_id == entity_id]

    def ingest_event(self, payload: WorldEventCreate) -> WorldEvent:
        entity = self.get_entity(payload.entity_id)
        if entity is None:
            raise ValueError("Entity not found")
        event = WorldEvent(**payload.model_dump())
        event.consequences = self._apply_consequences(entity, event)
        self._events.append(event)
        return event

    def list_events(self) -> list[WorldEvent]:
        return list(self._events)

    def snapshot(self) -> WorldSnapshot:
        entities = list(self._entities.values())
        return WorldSnapshot(
            entities=len(entities),
            relations=len(self._relations),
            events=len(self._events),
            active=sum(e.state == EntityState.active for e in entities),
            blocked=sum(e.state == EntityState.blocked for e in entities),
            degraded=sum(e.state == EntityState.degraded for e in entities),
            high_priority=sum(e.priority <= 2 for e in entities),
        )

    def _apply_consequences(self, entity: WorldEntity, event: WorldEvent) -> list[str]:
        consequences: list[str] = []
        if event.severity >= 5:
            entity.state = EntityState.blocked
            consequences.append(f"{entity.name} blocked due to critical event")
        elif event.severity == 4 and entity.state == EntityState.active:
            entity.state = EntityState.degraded
            consequences.append(f"{entity.name} degraded pending review")
        entity.updated_at = datetime.now(timezone.utc)

        for relation in self.list_relations(entity.id):
            if relation.source_id != entity.id:
                continue
            target = self.get_entity(relation.target_id)
            if target is None:
                continue
            if relation.kind == RelationKind.blocks and event.severity >= 4:
                target.state = EntityState.blocked
                target.updated_at = datetime.now(timezone.utc)
                consequences.append(f"{target.name} blocked by {entity.name}")
            elif relation.kind in {RelationKind.affects, RelationKind.triggers} and event.severity >= 4:
                if target.state == EntityState.active:
                    target.state = EntityState.degraded
                    target.updated_at = datetime.now(timezone.utc)
                    consequences.append(f"{target.name} degraded because of {entity.name}")
        return consequences


world_model_service = WorldModelService()
