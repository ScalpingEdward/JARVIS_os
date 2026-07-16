from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    OAuthCallbackRequest,
    OAuthStartRequest,
    OAuthStartResponse,
    PermissionConfirmation,
    SetupCreate,
    SetupListResponse,
    SetupPlatformStatus,
    SetupRecord,
)
from .service import connector_setup_service

router = APIRouter(prefix="/v1/connector-setup", tags=["connector-setup"])


@router.get("/status", response_model=SetupPlatformStatus)
def setup_status() -> SetupPlatformStatus:
    return connector_setup_service.status()


@router.post("/sessions", response_model=SetupRecord, status_code=status.HTTP_201_CREATED)
def create_setup(payload: SetupCreate) -> SetupRecord:
    return connector_setup_service.create(payload)


@router.get("/sessions", response_model=SetupListResponse)
def list_setups() -> SetupListResponse:
    items = connector_setup_service.list_all()
    return SetupListResponse(items=items, count=len(items))


@router.get("/sessions/{setup_id}", response_model=SetupRecord)
def get_setup(setup_id: UUID) -> SetupRecord:
    record = connector_setup_service.get(setup_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Setup session not found")
    return record


@router.post("/sessions/{setup_id}/permissions", response_model=SetupRecord)
def confirm_permissions(setup_id: UUID, payload: PermissionConfirmation) -> SetupRecord:
    try:
        record = connector_setup_service.confirm_permissions(setup_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Setup session not found")
    return record


@router.post("/sessions/{setup_id}/oauth/start", response_model=OAuthStartResponse)
def start_oauth(setup_id: UUID, payload: OAuthStartRequest) -> OAuthStartResponse:
    try:
        result = connector_setup_service.start_oauth(setup_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Setup session not found")
    return result


@router.post("/sessions/{setup_id}/oauth/callback", response_model=SetupRecord)
def complete_oauth(setup_id: UUID, payload: OAuthCallbackRequest) -> SetupRecord:
    try:
        record = connector_setup_service.complete_oauth(setup_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Setup session not found")
    return record


@router.post("/sessions/{setup_id}/test", response_model=SetupRecord)
def test_connection(setup_id: UUID) -> SetupRecord:
    record = connector_setup_service.test_connection(setup_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Setup session not found")
    return record


@router.post("/sessions/{setup_id}/finalize", response_model=SetupRecord)
def finalize_setup(setup_id: UUID) -> SetupRecord:
    try:
        record = connector_setup_service.finalize(setup_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Setup session not found")
    return record
