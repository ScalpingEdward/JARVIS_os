from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, VisionSignalAssessment, VisionSignalAssessmentCreate, VisionSignalStatusResponse
from .service import executive_telegram_chart_vision_signal_intelligence_service

router = APIRouter(tags=["executive-telegram-chart-vision-signal-intelligence"])
BASE = "/v1/executive-telegram-chart-vision-signal-intelligence"


@router.get(f"{BASE}/status", response_model=VisionSignalStatusResponse)
def vision_status(workspace_id: str = Query(min_length=1, max_length=100)) -> VisionSignalStatusResponse:
    return executive_telegram_chart_vision_signal_intelligence_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=VisionSignalAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: VisionSignalAssessmentCreate) -> VisionSignalAssessment:
    try:
        return executive_telegram_chart_vision_signal_intelligence_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[VisionSignalAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[VisionSignalAssessment]:
    return executive_telegram_chart_vision_signal_intelligence_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=VisionSignalAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> VisionSignalAssessment:
    item = executive_telegram_chart_vision_signal_intelligence_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vision signal assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def vision_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_telegram_chart_vision_signal_intelligence_service.audit(workspace_id)
