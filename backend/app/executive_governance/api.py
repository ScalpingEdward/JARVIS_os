from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ControlUpdate,
    ExecutiveGovernanceFramework,
    GovernanceFrameworkCreate,
    GovernanceListResponse,
    GovernanceStatusResponse,
)
from .service import executive_governance_service

router = APIRouter(tags=["executive-governance"])


@router.get("/v1/executive-governance/status", response_model=GovernanceStatusResponse)
def governance_status(workspace_id: str = Query(min_length=1, max_length=100)) -> GovernanceStatusResponse:
    return executive_governance_service.status(workspace_id)


@router.post("/v1/executive-governance/frameworks", response_model=ExecutiveGovernanceFramework, status_code=status.HTTP_201_CREATED)
def create_framework(payload: GovernanceFrameworkCreate) -> ExecutiveGovernanceFramework:
    try:
        return executive_governance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-governance/frameworks", response_model=GovernanceListResponse)
def list_frameworks(workspace_id: str = Query(min_length=1, max_length=100)) -> GovernanceListResponse:
    items = executive_governance_service.list_frameworks(workspace_id)
    return GovernanceListResponse(items=items, count=len(items))


@router.get("/v1/executive-governance/frameworks/{framework_id}", response_model=ExecutiveGovernanceFramework)
def get_framework(framework_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveGovernanceFramework:
    record = executive_governance_service.get(framework_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive governance framework not found")
    return record


@router.post("/v1/executive-governance/frameworks/{framework_id}/controls", response_model=ExecutiveGovernanceFramework)
def update_control(framework_id: UUID, payload: ControlUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveGovernanceFramework:
    try:
        return executive_governance_service.update_control(framework_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-governance/frameworks/{framework_id}/assess", response_model=ExecutiveGovernanceFramework)
def assess_framework(framework_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveGovernanceFramework:
    try:
        return executive_governance_service.assess(framework_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-governance/audit", response_model=list[AuditRecord])
def governance_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_governance_service.audit_records(workspace_id)
