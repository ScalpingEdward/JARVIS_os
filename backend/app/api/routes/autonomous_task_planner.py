from fastapi import APIRouter, HTTPException, Query

from app.schemas.autonomous_task_planner import TaskPlanAction, TaskPlanCreate, TaskPlanRecord
from app.services.autonomous_task_planner import autonomous_task_planner_service

router = APIRouter(prefix="/v1/autonomous-task-planner", tags=["autonomous-task-planner"])


@router.get("/status")
def status() -> dict:
    return autonomous_task_planner_service.status()


@router.post("/records", response_model=TaskPlanRecord)
def create_record(payload: TaskPlanCreate) -> TaskPlanRecord:
    try:
        return autonomous_task_planner_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[TaskPlanRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[TaskPlanRecord]:
    return autonomous_task_planner_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=TaskPlanRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> TaskPlanRecord:
    try:
        return autonomous_task_planner_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=TaskPlanRecord)
def act(record_id: str, payload: TaskPlanAction) -> TaskPlanRecord:
    try:
        return autonomous_task_planner_service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return autonomous_task_planner_service.audit(workspace_id)
