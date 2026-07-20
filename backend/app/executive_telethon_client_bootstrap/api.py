from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, TelethonBootstrapAssessment, TelethonBootstrapAssessmentCreate, TelethonBootstrapStatusResponse
from .service import executive_telethon_client_bootstrap_service

router = APIRouter(tags=["executive-telethon-client-bootstrap"])
BASE = "/v1/executive-telethon-client-bootstrap"


@router.get(f"{BASE}/status", response_model=TelethonBootstrapStatusResponse)
def bootstrap_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TelethonBootstrapStatusResponse:
    return executive_telethon_client_bootstrap_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=TelethonBootstrapAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: TelethonBootstrapAssessmentCreate) -> TelethonBootstrapAssessment:
    try:
        return executive_telethon_client_bootstrap_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[TelethonBootstrapAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[TelethonBootstrapAssessment]:
    return executive_telethon_client_bootstrap_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=TelethonBootstrapAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TelethonBootstrapAssessment:
    item = executive_telethon_client_bootstrap_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Telethon bootstrap assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def bootstrap_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_telethon_client_bootstrap_service.audit(workspace_id)
