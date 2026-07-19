from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, IncidentRecoveryAssessment, RecoveryInput, RecoveryListResponse, RecoveryStatusResponse
from .service import executive_trading_incident_recovery_service

router = APIRouter(tags=["executive-trading-incident-recovery"])


@router.get("/v1/executive-trading-incident-recovery/status", response_model=RecoveryStatusResponse)
def recovery_status(workspace_id: str = Query(min_length=1, max_length=100)) -> RecoveryStatusResponse:
    return executive_trading_incident_recovery_service.status(workspace_id)


@router.post("/v1/executive-trading-incident-recovery/assessments", response_model=IncidentRecoveryAssessment, status_code=status.HTTP_201_CREATED)
def create_recovery_assessment(payload: RecoveryInput) -> IncidentRecoveryAssessment:
    try:
        return executive_trading_incident_recovery_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trading-incident-recovery/assessments", response_model=RecoveryListResponse)
def list_recovery_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> RecoveryListResponse:
    items = executive_trading_incident_recovery_service.list_assessments(workspace_id)
    return RecoveryListResponse(items=items, count=len(items))


@router.get("/v1/executive-trading-incident-recovery/assessments/{assessment_id}", response_model=IncidentRecoveryAssessment)
def get_recovery_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> IncidentRecoveryAssessment:
    item = executive_trading_incident_recovery_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trading incident recovery assessment not found")
    return item


@router.get("/v1/executive-trading-incident-recovery/audit", response_model=list[AuditRecord])
def recovery_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_trading_incident_recovery_service.audit_records(workspace_id)
