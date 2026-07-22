from fastapi import APIRouter, HTTPException, Query

from .models import AssuranceActionRequest, AssuranceAssessment, AssuranceAssessmentCreate, AuditEvent
from .service import ContinuousAssuranceError, ContinuousAssuranceService

router = APIRouter(prefix="/v1/continuous-assurance-attestation", tags=["continuous-assurance-attestation"])
service = ContinuousAssuranceService()


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/assessments", response_model=AssuranceAssessment)
def create_assessment(payload: AssuranceAssessmentCreate) -> AssuranceAssessment:
    try:
        return service.create(payload)
    except ContinuousAssuranceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessments", response_model=list[AssuranceAssessment])
def list_assessments(workspace_id: str = Query(min_length=1)) -> list[AssuranceAssessment]:
    return service.list(workspace_id)


@router.get("/assessments/{record_id}", response_model=AssuranceAssessment)
def get_assessment(record_id: str, workspace_id: str = Query(min_length=1)) -> AssuranceAssessment:
    try:
        return service.get(record_id, workspace_id)
    except ContinuousAssuranceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/assessments/{record_id}/actions", response_model=AssuranceAssessment)
def act_on_assessment(record_id: str, payload: AssuranceActionRequest, workspace_id: str = Query(min_length=1)) -> AssuranceAssessment:
    try:
        return service.act(record_id, workspace_id, payload)
    except ContinuousAssuranceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
