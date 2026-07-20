from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    TelegramSdkClientAssessment,
    TelegramSdkClientAssessmentCreate,
    TelegramSdkClientStatusResponse,
)
from .service import executive_telegram_sdk_client_service

router = APIRouter(tags=["executive-telegram-sdk-client"])
BASE = "/v1/executive-telegram-sdk-client"


@router.get(f"{BASE}/status", response_model=TelegramSdkClientStatusResponse)
def sdk_client_status(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> TelegramSdkClientStatusResponse:
    return executive_telegram_sdk_client_service.status(workspace_id)


@router.post(
    f"{BASE}/assessments",
    response_model=TelegramSdkClientAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: TelegramSdkClientAssessmentCreate) -> TelegramSdkClientAssessment:
    try:
        return executive_telegram_sdk_client_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[TelegramSdkClientAssessment])
def list_assessments(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> list[TelegramSdkClientAssessment]:
    return executive_telegram_sdk_client_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=TelegramSdkClientAssessment)
def get_assessment(
    assessment_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> TelegramSdkClientAssessment:
    item = executive_telegram_sdk_client_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Telegram SDK client assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def sdk_client_audit(
    workspace_id: str = Query(min_length=1, max_length=100),
) -> list[AuditRecord]:
    return executive_telegram_sdk_client_service.audit(workspace_id)
