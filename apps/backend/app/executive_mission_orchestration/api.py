from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalRequest,
    AuditRecord,
    OrchestrationCreate,
    OrchestrationListResponse,
    OrchestrationRecord,
    OrchestrationStatusResponse,
)
from .service import executive_mission_orchestration_service


router = APIRouter(tags=["executive-mission-orchestration"])


@router.get("/v1/executive-missions/status", response_model=OrchestrationStatusResponse)
def orchestration_status(workspace_id: str = Query(min_length=1, max_length=100)) -> OrchestrationStatusResponse:
    return executive_mission_orchestration_service.status(workspace_id)


@router.post(
    "/v1/executive-missions/orchestrations",
    response_model=OrchestrationRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_orchestration(payload: OrchestrationCreate) -> OrchestrationRecord:
    try:
        return executive_mission_orchestration_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-missions/orchestrations", response_model=OrchestrationListResponse)
def list_orchestrations(workspace_id: str = Query(min_length=1, max_length=100)) -> OrchestrationListResponse:
    items = executive_mission_orchestration_service.list_records(workspace_id)
    return OrchestrationListResponse(items=items, count=len(items))


@router.get("/v1/executive-missions/orchestrations/{orchestration_id}", response_model=OrchestrationRecord)
def get_orchestration(
    orchestration_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> OrchestrationRecord:
    record = executive_mission_orchestration_service.get(orchestration_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    return record


@router.post(
    "/v1/executive-missions/orchestrations/{orchestration_id}/analyze",
    response_model=OrchestrationRecord,
)
def analyze_orchestration(
    orchestration_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
    actor_id: str = Query(min_length=1, max_length=100),
) -> OrchestrationRecord:
    try:
        return executive_mission_orchestration_service.analyze(orchestration_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/v1/executive-missions/orchestrations/{orchestration_id}/approval",
    response_model=OrchestrationRecord,
)
def approve_orchestration(orchestration_id: UUID, payload: ApprovalRequest) -> OrchestrationRecord:
    try:
        return executive_mission_orchestration_service.approve(orchestration_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/v1/executive-missions/audit", response_model=list[AuditRecord])
def orchestration_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_mission_orchestration_service.audit_records(workspace_id)
