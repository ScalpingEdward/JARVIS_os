from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AssetCmdbStatus, AssetCreate, AssetRecord, AssetState, MetricsRecord,
    Mutation, RelationshipCreate, RelationshipRecord,
)
from .service import asset_cmdb_service as service

router = APIRouter(prefix="/v1/asset-cmdb", tags=["asset-cmdb"])


@router.get("/status", response_model=AssetCmdbStatus)
def get_status() -> AssetCmdbStatus:
    return service.status()


@router.post("/assets", response_model=AssetRecord, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate) -> AssetRecord:
    try:
        return service.create_asset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assets", response_model=list[AssetRecord])
def list_assets(
    workspace_id: str = Query(min_length=1, max_length=120),
    state: AssetState | None = None,
) -> list[AssetRecord]:
    return service.list_assets(workspace_id, state)


@router.get("/assets/{asset_id}", response_model=AssetRecord)
def get_asset(asset_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> AssetRecord:
    item = service.get_asset(asset_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return item


def _set_state(asset_id: UUID, workspace_id: str, payload: Mutation, target: AssetState) -> AssetRecord:
    try:
        item = service.set_state(asset_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned asset not found")
    return item


@router.post("/assets/{asset_id}/register", response_model=AssetRecord)
def register_asset(asset_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AssetRecord:
    return _set_state(asset_id, workspace_id, payload, AssetState.REGISTERED)


@router.post("/assets/{asset_id}/validate", response_model=AssetRecord)
def validate_asset(asset_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AssetRecord:
    return _set_state(asset_id, workspace_id, payload, AssetState.VALIDATED)


@router.post("/assets/{asset_id}/activate", response_model=AssetRecord)
def activate_asset(asset_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AssetRecord:
    return _set_state(asset_id, workspace_id, payload, AssetState.ACTIVE)


@router.post("/assets/{asset_id}/maintenance", response_model=AssetRecord)
def maintain_asset(asset_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AssetRecord:
    return _set_state(asset_id, workspace_id, payload, AssetState.MAINTENANCE)


@router.post("/assets/{asset_id}/retire", response_model=AssetRecord)
def retire_asset(asset_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AssetRecord:
    return _set_state(asset_id, workspace_id, payload, AssetState.RETIRED)


@router.post("/relationships", response_model=RelationshipRecord, status_code=status.HTTP_201_CREATED)
def create_relationship(payload: RelationshipCreate) -> RelationshipRecord:
    try:
        return service.create_relationship(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/relationships", response_model=list[RelationshipRecord])
def list_relationships(
    workspace_id: str = Query(min_length=1, max_length=120),
    asset_id: UUID | None = None,
) -> list[RelationshipRecord]:
    return service.list_relationships(workspace_id, asset_id)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
