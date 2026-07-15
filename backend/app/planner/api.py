from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import (
    ExecutionPlan,
    PlanGoal,
    PlanListResponse,
    PlanProgressResponse,
    PlannerPreviewResponse,
    StepStatusUpdate,
)
from .service import PlannerError, planner_service

router = APIRouter(prefix="/v1/planner", tags=["planner"])


@router.post("/plan", response_model=PlannerPreviewResponse)
def create_plan(payload: PlanGoal) -> PlannerPreviewResponse:
    plan = planner_service.create_plan(payload)
    return PlannerPreviewResponse(plan=plan, tasks_created=payload.create_tasks)


@router.get("/plans", response_model=PlanListResponse)
def list_plans() -> PlanListResponse:
    items = planner_service.list_plans()
    return PlanListResponse(items=items, count=len(items))


@router.get("/plans/{plan_id}", response_model=ExecutionPlan)
def get_plan(plan_id: UUID) -> ExecutionPlan:
    try:
        return planner_service.get(plan_id)
    except PlannerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/plans/{plan_id}/steps/{step_id}", response_model=ExecutionPlan)
def update_step(plan_id: UUID, step_id: UUID, payload: StepStatusUpdate) -> ExecutionPlan:
    try:
        return planner_service.update_step(plan_id, step_id, payload.status)
    except PlannerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plans/{plan_id}/progress", response_model=PlanProgressResponse)
def plan_progress(plan_id: UUID) -> PlanProgressResponse:
    try:
        return planner_service.progress(plan_id)
    except PlannerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
