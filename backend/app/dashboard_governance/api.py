from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    DashboardGovernanceMetrics,
    DashboardGovernanceStatus,
    DashboardViewCreate,
    DashboardViewRecord,
    DashboardViewUpdate,
    ViewMutation,
    ViewState,
)
from .service import dashboard_governance_service

router = APIRouter(prefix="/v1/dashboard-governance", tags=["dashboard-governance"])


@router.get("/status", response_model=DashboardGovernanceStatus)
def module_status() -> DashboardGovernanceStatus:
    return dashboard_governance_service.status()


@router.post("/views", response_model=DashboardViewRecord, status_code=status.HTTP_201_CREATED)
def create_view(payload: DashboardViewCreate) -> DashboardViewRecord:
    try:
        return dashboard_governance_service.create_view(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/views", response_model=list[DashboardViewRecord])
def list_views(
    workspace_id: str = Query(min_length=1, max_length=100),
    state_filter: ViewState | None = Query(default=None, alias="state"),
) -> list[DashboardViewRecord]:
    return dashboard_governance_service.list_views(workspace_id, state_filter)


@router.get("/views/{view_id}", response_model=DashboardViewRecord)
def get_view(view_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> DashboardViewRecord:
    item = dashboard_governance_service.get_view(view_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dashboard view not found")
    return item


@router.put("/views/{view_id}", response_model=DashboardViewRecord)
def update_view(
    view_id: UUID,
    payload: DashboardViewUpdate,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> DashboardViewRecord:
    try:
        item = dashboard_governance_service.update_view(view_id, workspace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="dashboard view not found")
    return item


def _mutate(view_id: UUID, workspace_id: str, payload: ViewMutation, target: ViewState) -> DashboardViewRecord:
    try:
        item = dashboard_governance_service.mutate_view(view_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="dashboard view not found")
    return item


@router.post("/views/{view_id}/review", response_model=DashboardViewRecord)
def submit_review(view_id: UUID, payload: ViewMutation, workspace_id: str = Query(min_length=1, max_length=100)) -> DashboardViewRecord:
    return _mutate(view_id, workspace_id, payload, ViewState.REVIEW)


@router.post("/views/{view_id}/return-to-draft", response_model=DashboardViewRecord)
def return_to_draft(view_id: UUID, payload: ViewMutation, workspace_id: str = Query(min_length=1, max_length=100)) -> DashboardViewRecord:
    return _mutate(view_id, workspace_id, payload, ViewState.DRAFT)


@router.post("/views/{view_id}/publish", response_model=DashboardViewRecord)
def publish_view(view_id: UUID, payload: ViewMutation, workspace_id: str = Query(min_length=1, max_length=100)) -> DashboardViewRecord:
    return _mutate(view_id, workspace_id, payload, ViewState.PUBLISHED)


@router.post("/views/{view_id}/archive", response_model=DashboardViewRecord)
def archive_view(view_id: UUID, payload: ViewMutation, workspace_id: str = Query(min_length=1, max_length=100)) -> DashboardViewRecord:
    return _mutate(view_id, workspace_id, payload, ViewState.ARCHIVED)


@router.get("/resolved-view", response_model=DashboardViewRecord)
def resolved_view(
    workspace_id: str = Query(min_length=1, max_length=100),
    role: str | None = Query(default=None, max_length=100),
) -> DashboardViewRecord:
    item = dashboard_governance_service.resolve_view(workspace_id, role)
    if item is None:
        raise HTTPException(status_code=404, detail="no published dashboard view available")
    return item


@router.get("/metrics", response_model=DashboardGovernanceMetrics)
def metrics(workspace_id: str = Query(min_length=1, max_length=100)) -> DashboardGovernanceMetrics:
    return dashboard_governance_service.metrics(workspace_id)


@router.get("/audit", response_model=list[dict])
def audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[dict]:
    return dashboard_governance_service.list_audit(workspace_id)
