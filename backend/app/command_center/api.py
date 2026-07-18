from fastapi import APIRouter, Query, status

from .models import (
    CommandCenterMetrics,
    CommandCenterOverview,
    CommandCenterStatus,
    DashboardFilter,
    SignalCreate,
    SignalRecord,
    TimelinePoint,
)
from .service import command_center_service as service

router = APIRouter(prefix="/v1/command-center", tags=["command-center"])


@router.get("/status", response_model=CommandCenterStatus)
def get_status() -> CommandCenterStatus:
    return service.status()


@router.post("/signals", response_model=SignalRecord, status_code=status.HTTP_201_CREATED)
def record_signal(payload: SignalCreate) -> SignalRecord:
    return service.record_signal(payload)


@router.post("/signals/query", response_model=list[SignalRecord])
def query_signals(payload: DashboardFilter) -> list[SignalRecord]:
    return service.list_signals(payload)


@router.get("/overview", response_model=CommandCenterOverview)
def overview(
    workspace_id: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=10, ge=1, le=100),
) -> CommandCenterOverview:
    return service.overview(workspace_id, limit)


@router.get("/timeline", response_model=list[TimelinePoint])
def timeline(
    workspace_id: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[TimelinePoint]:
    return service.timeline(workspace_id, limit)


@router.get("/metrics", response_model=CommandCenterMetrics)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> CommandCenterMetrics:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
