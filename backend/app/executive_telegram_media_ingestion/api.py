from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, IngestionStatusResponse, TelegramMediaIngestion, TelegramMediaIngestionCreate
from .service import executive_telegram_media_ingestion_service

router = APIRouter(tags=["executive-telegram-media-ingestion"])
BASE = "/v1/executive-telegram-media-ingestion"


@router.get(f"{BASE}/status", response_model=IngestionStatusResponse)
def ingestion_status(workspace_id: str = Query(min_length=1, max_length=100)) -> IngestionStatusResponse:
    return executive_telegram_media_ingestion_service.status(workspace_id)


@router.post(f"{BASE}/ingestions", response_model=TelegramMediaIngestion, status_code=status.HTTP_201_CREATED)
def create_ingestion(payload: TelegramMediaIngestionCreate) -> TelegramMediaIngestion:
    try:
        return executive_telegram_media_ingestion_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/ingestions", response_model=list[TelegramMediaIngestion])
def list_ingestions(workspace_id: str = Query(min_length=1, max_length=100)) -> list[TelegramMediaIngestion]:
    return executive_telegram_media_ingestion_service.list_ingestions(workspace_id)


@router.get(f"{BASE}/ingestions/{{ingestion_id}}", response_model=TelegramMediaIngestion)
def get_ingestion(ingestion_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TelegramMediaIngestion:
    item = executive_telegram_media_ingestion_service.get(ingestion_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Telegram media ingestion not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def ingestion_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_telegram_media_ingestion_service.audit(workspace_id)
