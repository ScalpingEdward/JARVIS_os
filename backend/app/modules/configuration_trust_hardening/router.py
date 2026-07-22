from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, TrustActionRequest, TrustAssessment, TrustAssessmentCreate
from .service import ConfigurationTrustHardeningError, service

router = APIRouter(prefix="/v1/configuration-trust-hardening", tags=["configuration-trust-hardening"])


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/assessments", response_model=TrustAssessment)
def create_assessment(payload: TrustAssessmentCreate) -> TrustAssessment:
    try:
        return service.create(payload)
    except ConfigurationTrustHardeningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessments", response_model=list[TrustAssessment])
def list_assessments(workspace_id: str = Query(min_length=1)) -> list[TrustAssessment]:
    return service.list(workspace_id)


@router.get("/assessments/{record_id}", response_model=TrustAssessment)
def get_assessment(record_id: str, workspace_id: str = Query(min_length=1)) -> TrustAssessment:
    try:
        return service.get(record_id, workspace_id)
    except ConfigurationTrustHardeningError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/assessments/{record_id}/actions", response_model=TrustAssessment)
def action(record_id: str, payload: TrustActionRequest, workspace_id: str = Query(min_length=1)) -> TrustAssessment:
    try:
        return service.act(record_id, workspace_id, payload)
    except ConfigurationTrustHardeningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
