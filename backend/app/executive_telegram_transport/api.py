from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, TelegramTransportAssessment, TelegramTransportAssessmentCreate, TelegramTransportStatusResponse
from .service import executive_telegram_transport_service

router = APIRouter(tags=["executive-telegram-transport"])
BASE = "/v1/executive-telegram-transport"


@router.get(f"{BASE}/status", response_model=TelegramTransportStatusResponse)
def transport_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TelegramTransportStatusResponse:
    return executive_telegram_transport_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=TelegramTransportAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: TelegramTransportAssessmentCreate) -> TelegramTransportAssessment:
    try:
        return executive_telegram_transport_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[TelegramTransportAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[TelegramTransportAssessment]:
    return executive_telegram_transport_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=TelegramTransportAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TelegramTransportAssessment:
    item = executive_telegram_transport_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Telegram transport assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def transport_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_telegram_transport_service.audit(workspace_id)
