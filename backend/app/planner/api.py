from fastapi import APIRouter

from .models import PlanGoal, PlannerPreviewResponse
from .service import planner_service

router = APIRouter(prefix="/v1/planner", tags=["planner"])


@router.post("/plan", response_model=PlannerPreviewResponse)
def create_plan(payload: PlanGoal) -> PlannerPreviewResponse:
    plan = planner_service.create_plan(payload)
    return PlannerPreviewResponse(plan=plan, tasks_created=payload.create_tasks)
