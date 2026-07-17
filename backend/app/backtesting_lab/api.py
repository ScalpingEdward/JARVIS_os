from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    BacktestComparison,
    BacktestComparisonRequest,
    BacktestJob,
    BacktestJobCreate,
    BacktestingLabStatus,
)
from .service import backtesting_lab_service

router = APIRouter(prefix="/v1/backtesting-lab", tags=["backtesting-lab"])


@router.get("/status", response_model=BacktestingLabStatus)
def get_status() -> BacktestingLabStatus:
    return backtesting_lab_service.status()


@router.post("/jobs", response_model=BacktestJob, status_code=status.HTTP_201_CREATED)
def create_job(payload: BacktestJobCreate) -> BacktestJob:
    return backtesting_lab_service.create(payload)


@router.get("/jobs", response_model=list[BacktestJob])
def list_jobs() -> list[BacktestJob]:
    return backtesting_lab_service.list_all()


@router.get("/jobs/{job_id}", response_model=BacktestJob)
def get_job(job_id: UUID) -> BacktestJob:
    job = backtesting_lab_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Backtest job not found")
    return job


@router.post("/compare", response_model=BacktestComparison)
def compare_jobs(payload: BacktestComparisonRequest) -> BacktestComparison:
    try:
        return backtesting_lab_service.compare(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
