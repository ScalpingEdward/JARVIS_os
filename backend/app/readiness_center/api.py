from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ReadinessRun, ReadinessRunCreate, ReadinessRunList, ReadinessStatus
from .service import readiness_center_service


router = APIRouter(prefix="/v1/readiness-center", tags=["readiness-center"])


@router.get("/status", response_model=ReadinessStatus)
def readiness_status() -> ReadinessStatus:
    return readiness_center_service.status()


@router.post("/runs", response_model=ReadinessRun, status_code=status.HTTP_201_CREATED)
def run_preflight(payload: ReadinessRunCreate) -> ReadinessRun:
    return readiness_center_service.run(payload)


@router.get("/runs", response_model=ReadinessRunList)
def list_runs() -> ReadinessRunList:
    items = readiness_center_service.list_all()
    return ReadinessRunList(items=items, count=len(items))


@router.get("/runs/latest", response_model=ReadinessRun)
def latest_run() -> ReadinessRun:
    item = readiness_center_service.latest()
    if item is None:
        raise HTTPException(status_code=404, detail="No readiness run available")
    return item


@router.get("/runs/{run_id}", response_model=ReadinessRun)
def get_run(run_id: UUID) -> ReadinessRun:
    item = readiness_center_service.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Readiness run not found")
    return item
