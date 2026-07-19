from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, TreasuryAssessment, TreasuryAssessmentCreate, TreasuryStatusResponse
from .service import executive_treasury_wealth_governance_service

router = APIRouter(prefix="/v1/executive-treasury-wealth-governance", tags=["executive-treasury-wealth-governance"])


@router.get("/status", response_model=TreasuryStatusResponse)
def status_view(workspace_id: str = Query(min_length=1, max_length=100)) -> TreasuryStatusResponse:
    return executive_treasury_wealth_governance_service.status(workspace_id)


@router.post("/assessments", response_model=TreasuryAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: TreasuryAssessmentCreate) -> TreasuryAssessment:
    try:
        return executive_treasury_wealth_governance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessments", response_model=list[TreasuryAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[TreasuryAssessment]:
    return executive_treasury_wealth_governance_service.list(workspace_id)


@router.get("/assessments/{assessment_id}", response_model=TreasuryAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> TreasuryAssessment:
    item = executive_treasury_wealth_governance_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Treasury assessment not found")
    return item


@router.get("/audit", response_model=list[AuditRecord])
def audit_view(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_treasury_wealth_governance_service.audit(workspace_id)
