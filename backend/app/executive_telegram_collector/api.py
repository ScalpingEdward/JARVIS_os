from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, TelegramCollectorAssessment, TelegramCollectorAssessmentCreate, TelegramCollectorStatusResponse
from .service import executive_telegram_collector_service

router = APIRouter(tags=["executive-telegram-collector"])
BASE = "/v1/executive-telegram-collector"


@router.get(f"{BASE}/status", response_model=TelegramCollectorStatusResponse)
def collector_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TelegramCollectorStatusResponse:
    return executive_telegram_collector_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=TelegramCollectorAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: TelegramCollectorAssessmentCreate) -> TelegramCollectorAssessment:
    try:
        return executive_telegram_collector_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[TelegramCollectorAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[TelegramCollectorAssessment]:
    return executive_telegram_collector_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=TelegramCollectorAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TelegramCollectorAssessment:
    item = executive_telegram_collector_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Telegram collector assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def collector_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_telegram_collector_service.audit(workspace_id)
