from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    MilestoneUpdate,
    PlanActivation,
    PlanListResponse,
    StrategicPlanCreate,
    StrategicPlanRecord,
    StrategicPlannerStatus,
)
from .service import strategic_planner_service

router = APIRouter(prefix="/v1/strategic-plans", tags=["strategic-planner"])


@router.get("/status", response_model=StrategicPlannerStatus)
def planner_status() -> StrategicPlannerStatus:
    return strategic_planner_service.status()


@router.post("", response_model=StrategicPlanRecord, status_code=status.HTTP_201_CREATED)
def create_plan(payload: StrategicPlanCreate) -> StrategicPlanRecord:
    return strategic_planner_service.create(payload)


@router.get("", response_model=PlanListResponse)
def list_plans() -> PlanListResponse:
    items = strategic_planner_service.list_all()
    return PlanListResponse(items=items, count=len(items))


@router.get("/{plan_id}", response_model=StrategicPlanRecord)
def get_plan(plan_id: UUID) -> StrategicPlanRecord:
    plan = strategic_planner_service.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Strategic plan not found")
    return plan


@router.post("/{plan_id}/activate", response_model=StrategicPlanRecord)
def activate_plan(plan_id: UUID, payload: PlanActivation) -> StrategicPlanRecord:
    plan = strategic_planner_service.activate(plan_id, payload)
    if plan is None:
        raise HTTPException(status_code=404, detail="Strategic plan not found")
    return plan


@router.patch("/{plan_id}/milestones/{milestone_id}", response_model=StrategicPlanRecord)
def update_milestone(plan_id: UUID, milestone_id: UUID, payload: MilestoneUpdate) -> StrategicPlanRecord:
    plan = strategic_planner_service.update_milestone(plan_id, milestone_id, payload)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan or milestone not found")
    return plan
