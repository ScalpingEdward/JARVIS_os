from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, EventBusAssessment, EventBusAssessmentCreate, EventBusStatusResponse
from .service import executive_event_bus_service

router = APIRouter(tags=["executive-event-bus"])
BASE = "/v1/executive-event-bus"


@router.get(f"{BASE}/status", response_model=EventBusStatusResponse)
def event_bus_status(workspace_id: str = Query(min_length=1, max_length=100)) -> EventBusStatusResponse:
    return executive_event_bus_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=EventBusAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: EventBusAssessmentCreate) -> EventBusAssessment:
    try:
        return executive_event_bus_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[EventBusAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[EventBusAssessment]:
    return executive_event_bus_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=EventBusAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> EventBusAssessment:
    item = executive_event_bus_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Event-bus assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def event_bus_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_event_bus_service.audit(workspace_id)
