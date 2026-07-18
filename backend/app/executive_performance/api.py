from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, MeasurementUpdate, PerformanceStatusResponse, Scorecard, ScorecardCreate, ScorecardList
from .service import executive_performance_service

router = APIRouter(tags=["executive-performance"])


@router.get("/v1/executive-performance/status", response_model=PerformanceStatusResponse)
def performance_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PerformanceStatusResponse:
    return executive_performance_service.status(workspace_id)


@router.post("/v1/executive-performance/scorecards", response_model=Scorecard, status_code=status.HTTP_201_CREATED)
def create_scorecard(payload: ScorecardCreate) -> Scorecard:
    try:
        return executive_performance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-performance/scorecards", response_model=ScorecardList)
def list_scorecards(workspace_id: str = Query(min_length=1, max_length=100)) -> ScorecardList:
    items = executive_performance_service.list_scorecards(workspace_id)
    return ScorecardList(items=items, count=len(items))


@router.get("/v1/executive-performance/scorecards/{scorecard_id}", response_model=Scorecard)
def get_scorecard(scorecard_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> Scorecard:
    record = executive_performance_service.get(scorecard_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Performance scorecard not found")
    return record


@router.post("/v1/executive-performance/scorecards/{scorecard_id}/measurements", response_model=Scorecard)
def update_measurements(scorecard_id: UUID, payload: MeasurementUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> Scorecard:
    try:
        return executive_performance_service.update_measurements(scorecard_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-performance/scorecards/{scorecard_id}/analyze", response_model=Scorecard)
def analyze_scorecard(scorecard_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> Scorecard:
    try:
        return executive_performance_service.analyze(scorecard_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-performance/audit", response_model=list[AuditRecord])
def performance_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_performance_service.audit_records(workspace_id)
