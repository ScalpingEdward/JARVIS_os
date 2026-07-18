from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..planning_portfolio.api import router as planning_portfolio_router
from .models import (
    ApprovalRequest,
    AuditRecord,
    GoalCreate,
    GoalRecord,
    MissionHandoffPreview,
    PlanCreate,
    PlanRecord,
    PlanningStatus,
    SimulationRecord,
    SimulationRequest,
)
from .service import planning_intelligence_service

router = APIRouter(prefix="/v1/planning", tags=["planning-intelligence"])


@router.get("/status", response_model=PlanningStatus)
def planning_status(workspace_id: str = Query(min_length=1, max_length=120)) -> PlanningStatus:
    return planning_intelligence_service.status(workspace_id)


@router.post("/goals", response_model=GoalRecord, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate) -> GoalRecord:
    try:
        return planning_intelligence_service.create_goal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/goals", response_model=list[GoalRecord])
def list_goals(workspace_id: str = Query(min_length=1, max_length=120)) -> list[GoalRecord]:
    return planning_intelligence_service.list_goals(workspace_id)


@router.get("/goals/{goal_id}/tree", response_model=list[GoalRecord])
def goal_tree(goal_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> list[GoalRecord]:
    try:
        return planning_intelligence_service.goal_tree(workspace_id, goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plans", response_model=PlanRecord, status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanCreate) -> PlanRecord:
    try:
        return planning_intelligence_service.create_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plans", response_model=list[PlanRecord])
def list_plans(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PlanRecord]:
    return planning_intelligence_service.list_plans(workspace_id)


@router.get("/plans/{plan_id}", response_model=PlanRecord)
def get_plan(plan_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> PlanRecord:
    record = planning_intelligence_service.get_plan(workspace_id, plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="plan not found")
    return record


@router.post("/plans/{plan_id}/simulate", response_model=SimulationRecord)
def simulate_plan(plan_id: UUID, payload: SimulationRequest) -> SimulationRecord:
    try:
        return planning_intelligence_service.simulate(plan_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/approve", response_model=PlanRecord)
def approve_plan(plan_id: UUID, payload: ApprovalRequest) -> PlanRecord:
    try:
        return planning_intelligence_service.approve(plan_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plans/{plan_id}/mission-handoff-preview", response_model=MissionHandoffPreview)
def mission_handoff_preview(
    plan_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> MissionHandoffPreview:
    try:
        return planning_intelligence_service.mission_handoff_preview(workspace_id, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/archive", response_model=PlanRecord)
def archive_plan(
    plan_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
    actor_id: str = Query(min_length=1, max_length=120),
) -> PlanRecord:
    try:
        return planning_intelligence_service.archive(workspace_id, plan_id, actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditRecord])
def planning_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return planning_intelligence_service.audit(workspace_id)


router.include_router(planning_portfolio_router)
