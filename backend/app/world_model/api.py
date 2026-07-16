from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    EntityState,
    RelationCreate,
    WorldEntity,
    WorldEntityCreate,
    WorldEvent,
    WorldEventCreate,
    WorldRelation,
    WorldSnapshot,
)
from .service import world_model_service

router = APIRouter(prefix="/v1/world-model", tags=["world-model"])


@router.get("/status", response_model=WorldSnapshot)
def status_view() -> WorldSnapshot:
    return world_model_service.snapshot()


@router.post("/entities", response_model=WorldEntity, status_code=status.HTTP_201_CREATED)
def upsert_entity(payload: WorldEntityCreate) -> WorldEntity:
    return world_model_service.upsert_entity(payload)


@router.get("/entities", response_model=list[WorldEntity])
def list_entities(state: EntityState | None = None) -> list[WorldEntity]:
    return world_model_service.list_entities(state=state)


@router.get("/entities/{entity_id}", response_model=WorldEntity)
def get_entity(entity_id: UUID) -> WorldEntity:
    entity = world_model_service.get_entity(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="World entity not found")
    return entity


@router.post("/relations", response_model=WorldRelation, status_code=status.HTTP_201_CREATED)
def add_relation(payload: RelationCreate) -> WorldRelation:
    try:
        return world_model_service.add_relation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/relations", response_model=list[WorldRelation])
def list_relations(entity_id: UUID | None = None) -> list[WorldRelation]:
    return world_model_service.list_relations(entity_id=entity_id)


@router.post("/events", response_model=WorldEvent, status_code=status.HTTP_201_CREATED)
def ingest_event(payload: WorldEventCreate) -> WorldEvent:
    try:
        return world_model_service.ingest_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/events", response_model=list[WorldEvent])
def list_events() -> list[WorldEvent]:
    return world_model_service.list_events()
