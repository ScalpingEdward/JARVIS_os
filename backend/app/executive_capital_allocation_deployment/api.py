from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AllocationAssessment, AllocationInput, AllocationListResponse, AllocationStatusResponse, AuditRecord
from .service import executive_capital_allocation_deployment_service

router = APIRouter(tags=["executive-capital-allocation-deployment"])


@router.get("/v1/executive-capital-allocation-deployment/status", response_model=AllocationStatusResponse)
def allocation_status(workspace_id: str = Query(min_length=1, max_length=100)) -> AllocationStatusResponse:
    return executive_capital_allocation_deployment_service.status(workspace_id)


@router.post("/v1/executive-capital-allocation-deployment/assessments", response_model=AllocationAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AllocationInput) -> AllocationAssessment:
    try:
        return executive_capital_allocation_deployment_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-capital-allocation-deployment/assessments", response_model=AllocationListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> AllocationListResponse:
    items = executive_capital_allocation_deployment_service.list_assessments(workspace_id)
    return AllocationListResponse(items=items, count=len(items))


@router.get("/v1/executive-capital-allocation-deployment/assessments/{assessment_id}", response_model=AllocationAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> AllocationAssessment:
    item = executive_capital_allocation_deployment_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Capital allocation assessment not found")
    return item


@router.get("/v1/executive-capital-allocation-deployment/audit", response_model=list[AuditRecord])
def allocation_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_capital_allocation_deployment_service.audit_records(workspace_id)
