from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import service

router = APIRouter(prefix="/v1/code", tags=["code"])


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except service.CodeTaskError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class TaskIn(BaseModel):
    text: str = Field(min_length=8, max_length=4000)
    kind: str = "code"


class ReportIn(BaseModel):
    status: str
    summary: str | None = None
    diff: str | None = None
    tests: str | None = None
    branch: str | None = None
    error: str | None = None
    commit: str | None = None


@router.get("/tasks")
def list_tasks() -> list[dict]:
    return service.tasks()


@router.post("/tasks")
def create_task(payload: TaskIn) -> dict:
    return _guard(service.create, payload.text, "dashboard", payload.kind)


@router.post("/tasks/{task_id}/{action}")
def decide(task_id: str, action: str) -> dict:
    """Brano's buttons: approve / reject (a ready change), revert (an applied one)."""
    return _guard(service.decide, task_id, action)


@router.post("/runner/claim")
def claim() -> dict:
    return {"task": service.claim()}


@router.post("/runner/report/{task_id}")
def report(task_id: str, payload: ReportIn) -> dict:
    return _guard(service.report, task_id, **payload.model_dump())
