from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, CopyControlRequest, CopyGovernanceAssessment, CopyGovernanceAssessmentCreate, CopyGovernanceStatusResponse
from .service import executive_multi_account_copy_governance_service

router = APIRouter(tags=["executive-multi-account-copy-governance"])


@router.get("/v1/executive-multi-account-copy-governance/status", response_model=CopyGovernanceStatusResponse)
def copy_status(workspace_id: str = Query(min_length=1, max_length=100)) -> CopyGovernanceStatusResponse:
    return executive_multi_account_copy_governance_service.status(workspace_id)


@router.post("/v1/executive-multi-account-copy-governance/assessments", response_model=CopyGovernanceAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: CopyGovernanceAssessmentCreate) -> CopyGovernanceAssessment:
    try:
        return executive_multi_account_copy_governance_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-multi-account-copy-governance/assessments", response_model=list[CopyGovernanceAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[CopyGovernanceAssessment]:
    return executive_multi_account_copy_governance_service.list_groups(workspace_id)


@router.get("/v1/executive-multi-account-copy-governance/assessments/{record_id}", response_model=CopyGovernanceAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> CopyGovernanceAssessment:
    record = executive_multi_account_copy_governance_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Copy governance record not found")
    return record


def _control(request: CopyControlRequest, suspend: bool) -> CopyGovernanceAssessment:
    try:
        return executive_multi_account_copy_governance_service.control(request, suspend=suspend)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-multi-account-copy-governance/suspend", response_model=CopyGovernanceAssessment)
def suspend_copy_group(request: CopyControlRequest) -> CopyGovernanceAssessment:
    return _control(request, True)


@router.post("/v1/executive-multi-account-copy-governance/resume", response_model=CopyGovernanceAssessment)
def resume_copy_group(request: CopyControlRequest) -> CopyGovernanceAssessment:
    return _control(request, False)


@router.get("/v1/executive-multi-account-copy-governance/audit", response_model=list[AuditRecord])
def copy_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_multi_account_copy_governance_service.audit_records(workspace_id)
