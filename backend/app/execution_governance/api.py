from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import ApprovalRequest, AuditRecord, ExecutionRelease, GovernanceStatus, ReleaseCreate, ReleaseListResponse
from .service import execution_governance_service

router = APIRouter(tags=["execution-governance"])


@router.get("/v1/execution-governance/status", response_model=GovernanceStatus)
def governance_status(workspace_id: str = Query(min_length=1, max_length=100)) -> GovernanceStatus:
    return execution_governance_service.status(workspace_id)


@router.post("/v1/execution-governance/releases", response_model=ExecutionRelease, status_code=status.HTTP_201_CREATED)
def create_release(payload: ReleaseCreate) -> ExecutionRelease:
    try:
        return execution_governance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/execution-governance/releases", response_model=ReleaseListResponse)
def list_releases(workspace_id: str = Query(min_length=1, max_length=100)) -> ReleaseListResponse:
    items = execution_governance_service.list_records(workspace_id)
    return ReleaseListResponse(items=items, count=len(items))


@router.get("/v1/execution-governance/releases/{release_id}", response_model=ExecutionRelease)
def get_release(release_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutionRelease:
    record = execution_governance_service.get(release_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Release not found")
    return record


@router.post("/v1/execution-governance/releases/{release_id}/validate", response_model=ExecutionRelease)
def validate_release(release_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutionRelease:
    try:
        return execution_governance_service.validate(release_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/execution-governance/releases/{release_id}/approval", response_model=ExecutionRelease)
def approve_release(release_id: UUID, payload: ApprovalRequest) -> ExecutionRelease:
    try:
        return execution_governance_service.approve(release_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/v1/execution-governance/audit", response_model=list[AuditRecord])
def audit_records(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return execution_governance_service.audit_records(workspace_id)
