from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AssessmentListResponse, AuditRecord, FormationAssessment, FormationAssessmentCreate, StatusResponse
from .service import executive_prop_payout_capital_formation_service

router = APIRouter(tags=["executive-prop-payout-capital-formation"])


@router.get("/v1/executive-prop-payout-capital-formation/status", response_model=StatusResponse)
def formation_status(workspace_id: str = Query(min_length=1, max_length=100)) -> StatusResponse:
    return executive_prop_payout_capital_formation_service.status(workspace_id)


@router.post(
    "/v1/executive-prop-payout-capital-formation/assessments",
    response_model=FormationAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: FormationAssessmentCreate) -> FormationAssessment:
    try:
        return executive_prop_payout_capital_formation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-prop-payout-capital-formation/assessments", response_model=AssessmentListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> AssessmentListResponse:
    items = executive_prop_payout_capital_formation_service.list_assessments(workspace_id)
    return AssessmentListResponse(items=items, count=len(items))


@router.get("/v1/executive-prop-payout-capital-formation/assessments/{assessment_id}", response_model=FormationAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> FormationAssessment:
    record = executive_prop_payout_capital_formation_service.get(assessment_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formation assessment not found")
    return record


@router.get("/v1/executive-prop-payout-capital-formation/audit", response_model=list[AuditRecord])
def formation_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_prop_payout_capital_formation_service.audit_records(workspace_id)
