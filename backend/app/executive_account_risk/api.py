from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AccountRiskAssessment, AccountRiskAssessmentCreate, AccountRiskStatusResponse, AuditRecord, RiskReductionRequest
from .service import executive_account_risk_service

router = APIRouter(tags=["executive-account-risk"])


@router.get("/v1/executive-account-risk/status", response_model=AccountRiskStatusResponse)
def account_risk_status(workspace_id: str = Query(min_length=1, max_length=100)) -> AccountRiskStatusResponse:
    return executive_account_risk_service.status(workspace_id)


@router.post("/v1/executive-account-risk/assessments", response_model=AccountRiskAssessment, status_code=status.HTTP_201_CREATED)
def create_account_risk_assessment(payload: AccountRiskAssessmentCreate) -> AccountRiskAssessment:
    try:
        return executive_account_risk_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-account-risk/assessments", response_model=list[AccountRiskAssessment])
def list_account_risk_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AccountRiskAssessment]:
    return executive_account_risk_service.list_assessments(workspace_id)


@router.get("/v1/executive-account-risk/assessments/{record_id}", response_model=AccountRiskAssessment)
def get_account_risk_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> AccountRiskAssessment:
    record = executive_account_risk_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Account-risk assessment not found")
    return record


@router.post("/v1/executive-account-risk/reduce", response_model=AccountRiskAssessment)
def reduce_account_risk(request: RiskReductionRequest) -> AccountRiskAssessment:
    try:
        return executive_account_risk_service.reduce(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-account-risk/audit", response_model=list[AuditRecord])
def account_risk_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_account_risk_service.audit_records(workspace_id)
