from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ContainmentActionRequest,
    ContainmentReleaseRequest,
    EmergencyContainmentAssessment,
    EmergencyContainmentAssessmentCreate,
    EmergencyContainmentStatusResponse,
)
from .service import executive_emergency_risk_containment_service

router = APIRouter(tags=["executive-emergency-risk-containment"])


@router.get("/v1/executive-emergency-risk-containment/status", response_model=EmergencyContainmentStatusResponse)
def containment_status(workspace_id: str = Query(min_length=1, max_length=100)) -> EmergencyContainmentStatusResponse:
    return executive_emergency_risk_containment_service.status(workspace_id)


@router.post("/v1/executive-emergency-risk-containment/assessments", response_model=EmergencyContainmentAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: EmergencyContainmentAssessmentCreate) -> EmergencyContainmentAssessment:
    try:
        return executive_emergency_risk_containment_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-emergency-risk-containment/assessments", response_model=list[EmergencyContainmentAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[EmergencyContainmentAssessment]:
    return executive_emergency_risk_containment_service.list_assessments(workspace_id)


@router.get("/v1/executive-emergency-risk-containment/assessments/{record_id}", response_model=EmergencyContainmentAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> EmergencyContainmentAssessment:
    record = executive_emergency_risk_containment_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Emergency containment record not found")
    return record


@router.post("/v1/executive-emergency-risk-containment/contain", response_model=EmergencyContainmentAssessment)
def contain_account(request: ContainmentActionRequest) -> EmergencyContainmentAssessment:
    try:
        return executive_emergency_risk_containment_service.contain(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-emergency-risk-containment/release", response_model=EmergencyContainmentAssessment)
def release_account(request: ContainmentReleaseRequest) -> EmergencyContainmentAssessment:
    try:
        return executive_emergency_risk_containment_service.release(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-emergency-risk-containment/audit", response_model=list[AuditRecord])
def containment_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_emergency_risk_containment_service.audit_records(workspace_id)
