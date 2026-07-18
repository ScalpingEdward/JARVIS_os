from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AnalysisCreate, AnalysisRecord, AnalysisState, DependencyCreate,
    DependencyImpactStatus, DependencyRecord, GraphNodeCreate, GraphNodeRecord,
    MetricsRecord, Mutation,
)
from .service import dependency_impact_service as service

router = APIRouter(prefix="/v1/dependency-impact", tags=["dependency-impact"])


@router.get("/status", response_model=DependencyImpactStatus)
def get_status() -> DependencyImpactStatus:
    return service.status()


@router.post("/nodes", response_model=GraphNodeRecord, status_code=status.HTTP_201_CREATED)
def create_node(payload: GraphNodeCreate) -> GraphNodeRecord:
    try:
        return service.create_node(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/nodes", response_model=list[GraphNodeRecord])
def list_nodes(workspace_id: str = Query(min_length=1, max_length=120)) -> list[GraphNodeRecord]:
    return service.list_nodes(workspace_id)


@router.get("/nodes/{node_id}", response_model=GraphNodeRecord)
def get_node(node_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> GraphNodeRecord:
    item = service.get_node(node_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Dependency node not found")
    return item


@router.post("/dependencies", response_model=DependencyRecord, status_code=status.HTTP_201_CREATED)
def create_dependency(payload: DependencyCreate) -> DependencyRecord:
    try:
        return service.create_dependency(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/dependencies", response_model=list[DependencyRecord])
def list_dependencies(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DependencyRecord]:
    return service.list_dependencies(workspace_id)


@router.post("/analyses", response_model=AnalysisRecord, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: AnalysisCreate) -> AnalysisRecord:
    try:
        return service.create_analysis(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/analyses", response_model=list[AnalysisRecord])
def list_analyses(
    workspace_id: str = Query(min_length=1, max_length=120),
    state: AnalysisState | None = None,
) -> list[AnalysisRecord]:
    return service.list_analyses(workspace_id, state)


@router.get("/analyses/{analysis_id}", response_model=AnalysisRecord)
def get_analysis(analysis_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> AnalysisRecord:
    item = service.get_analysis(analysis_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Impact analysis not found")
    return item


def _set_analysis(analysis_id: UUID, workspace_id: str, payload: Mutation, target: AnalysisState) -> AnalysisRecord:
    try:
        item = service.set_analysis_state(analysis_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned impact analysis not found")
    return item


@router.post("/analyses/{analysis_id}/review", response_model=AnalysisRecord)
def review_analysis(analysis_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AnalysisRecord:
    return _set_analysis(analysis_id, workspace_id, payload, AnalysisState.REVIEWED)


@router.post("/analyses/{analysis_id}/approve", response_model=AnalysisRecord)
def approve_analysis(analysis_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AnalysisRecord:
    return _set_analysis(analysis_id, workspace_id, payload, AnalysisState.APPROVED)


@router.post("/analyses/{analysis_id}/archive", response_model=AnalysisRecord)
def archive_analysis(analysis_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AnalysisRecord:
    return _set_analysis(analysis_id, workspace_id, payload, AnalysisState.ARCHIVED)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
