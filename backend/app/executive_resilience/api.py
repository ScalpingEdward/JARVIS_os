from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ContinuityUpdate,
    ExecutiveResiliencePlan,
    ResilienceListResponse,
    ResiliencePlanCreate,
    ResilienceStatusResponse,
)
from .service import executive_resilience_service

router = APIRouter(tags=["executive-resilience"])


@router.get("/v1/executive-resilience/status", response_model=ResilienceStatusResponse)
def resilience_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ResilienceStatusResponse:
    return executive_resilience_service.status(workspace_id)


@router.post("/v1/executive-resilience/plans", response_model=ExecutiveResiliencePlan, status_code=status.HTTP_201_CREATED)
def create_plan(payload: ResiliencePlanCreate) -> ExecutiveResiliencePlan:
    try:
        return executive_resilience_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-resilience/plans", response_model=ResilienceListResponse)
def list_plans(workspace_id: str = Query(min_length=1, max_length=100)) -> ResilienceListResponse:
    items = executive_resilience_service.list_plans(workspace_id)
    return ResilienceListResponse(items=items, count=len(items))


@router.get("/v1/executive-resilience/plans/{plan_id}", response_model=ExecutiveResiliencePlan)
def get_plan(plan_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveResiliencePlan:
    record = executive_resilience_service.get(plan_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive resilience plan not found")
    return record


@router.post("/v1/executive-resilience/plans/{plan_id}/continuity", response_model=ExecutiveResiliencePlan)
def update_continuity(plan_id: UUID, payload: ContinuityUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveResiliencePlan:
    try:
        return executive_resilience_service.update_continuity(plan_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-resilience/plans/{plan_id}/assess", response_model=ExecutiveResiliencePlan)
def assess_plan(plan_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveResiliencePlan:
    try:
        return executive_resilience_service.assess(plan_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-resilience/audit", response_model=list[AuditRecord])
def resilience_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_resilience_service.audit_records(workspace_id)
