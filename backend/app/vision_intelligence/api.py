from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AnalysisRequest,
    AssetMutation,
    AuditRecord,
    VisionAnalysisRecord,
    VisionAssetCreate,
    VisionAssetRecord,
    VisionIntelligenceStatus,
)
from .service import vision_intelligence_service


router = APIRouter(prefix="/v1/vision-intelligence", tags=["vision-intelligence"])


@router.get("/status", response_model=VisionIntelligenceStatus)
def vision_status() -> VisionIntelligenceStatus:
    return vision_intelligence_service.status()


@router.post("/assets", response_model=VisionAssetRecord, status_code=status.HTTP_201_CREATED)
def create_asset(payload: VisionAssetCreate) -> VisionAssetRecord:
    try:
        return vision_intelligence_service.create_asset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assets", response_model=list[VisionAssetRecord])
def list_assets(workspace_id: str = Query(min_length=1, max_length=120), include_inactive: bool = False) -> list[VisionAssetRecord]:
    return vision_intelligence_service.list_assets(workspace_id, include_inactive)


@router.get("/assets/{asset_id}", response_model=VisionAssetRecord)
def get_asset(asset_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> VisionAssetRecord:
    item = vision_intelligence_service.get_asset(asset_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vision asset not found")
    return item


@router.post("/assets/{asset_id}/archive", response_model=VisionAssetRecord)
def archive_asset(asset_id: UUID, payload: AssetMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> VisionAssetRecord:
    item = vision_intelligence_service.set_active(asset_id, workspace_id, payload, False)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned vision asset not found")
    return item


@router.post("/assets/{asset_id}/restore", response_model=VisionAssetRecord)
def restore_asset(asset_id: UUID, payload: AssetMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> VisionAssetRecord:
    item = vision_intelligence_service.set_active(asset_id, workspace_id, payload, True)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned vision asset not found")
    return item


@router.post("/analyses", response_model=VisionAnalysisRecord, status_code=status.HTTP_201_CREATED)
def analyze_asset(payload: AnalysisRequest) -> VisionAnalysisRecord:
    return vision_intelligence_service.analyze(payload)


@router.get("/analyses", response_model=list[VisionAnalysisRecord])
def list_analyses(workspace_id: str = Query(min_length=1, max_length=120), asset_id: UUID | None = None) -> list[VisionAnalysisRecord]:
    return vision_intelligence_service.list_analyses(workspace_id, asset_id)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return vision_intelligence_service.list_audit(workspace_id)
