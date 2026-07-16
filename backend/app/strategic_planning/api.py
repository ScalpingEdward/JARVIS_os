from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ProgressUpdate, StrategicGoal, StrategicGoalCreate, StrategicPlan, StrategicPlanningStatus
from .service import strategic_planning_service


router = APIRouter(prefix="/v1/strategic-planning", tags=["strategic-planning"])


@router.get("/status", response_model=StrategicPlanningStatus)
def planning_status() -> StrategicPlanningStatus:
    return strategic_planning_service.status()


@router.post("/goals", response_model=StrategicGoal, status_code=status.HTTP_201_CREATED)
def create_goal(payload: StrategicGoalCreate) -> StrategicGoal:
    return strategic_planning_service.create(payload)


@router.get("/goals", response_model=list[StrategicGoal])
def list_goals() -> list[StrategicGoal]:
    return strategic_planning_service.list_all()


@router.get("/goals/{goal_id}", response_model=StrategicGoal)
def get_goal(goal_id: UUID) -> StrategicGoal:
    goal = strategic_planning_service.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Strategic goal not found")
    return goal


@router.patch("/goals/{goal_id}/progress", response_model=StrategicGoal)
def update_goal_progress(goal_id: UUID, payload: ProgressUpdate) -> StrategicGoal:
    goal = strategic_planning_service.update_progress(goal_id, payload)
    if goal is None:
        raise HTTPException(status_code=404, detail="Strategic goal not found")
    return goal


@router.get("/plan", response_model=StrategicPlan)
def generate_plan() -> StrategicPlan:
    return strategic_planning_service.plan()
