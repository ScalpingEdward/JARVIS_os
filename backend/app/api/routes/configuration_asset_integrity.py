from fastapi import APIRouter, HTTPException, Query

from app.schemas.configuration_asset_integrity import (
    ConfigurationAssetAction,
    ConfigurationAssetCreate,
    ConfigurationAssetRecord,
)
from app.services.configuration_asset_integrity import configuration_asset_integrity_service


router = APIRouter(prefix="/v1/configuration-asset-integrity", tags=["configuration-asset-integrity"])


@router.get("/status")
def status() -> dict:
    return configuration_asset_integrity_service.status()


@router.post("/records", response_model=ConfigurationAssetRecord)
def create_record(payload: ConfigurationAssetCreate) -> ConfigurationAssetRecord:
    try:
        return configuration_asset_integrity_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ConfigurationAssetRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ConfigurationAssetRecord]:
    return configuration_asset_integrity_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ConfigurationAssetRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ConfigurationAssetRecord:
    try:
        return configuration_asset_integrity_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ConfigurationAssetRecord)
def act_on_record(record_id: str, payload: ConfigurationAssetAction) -> ConfigurationAssetRecord:
    try:
        return configuration_asset_integrity_service.act(
            payload.workspace_id,
            record_id,
            payload.action,
            payload.actor,
            payload.operation_id,
            payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in configuration_asset_integrity_service.audit(workspace_id)]
