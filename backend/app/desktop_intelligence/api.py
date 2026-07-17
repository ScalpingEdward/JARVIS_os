from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalRequest,
    DesktopActionCreate,
    DesktopActionRecord,
    DesktopAuditRecord,
    DesktopIntelligenceStatus,
    DesktopSessionCreate,
    DesktopSessionRecord,
    DesktopSnapshotCreate,
    DesktopSnapshotRecord,
    SessionMutation,
    SessionState,
)
from .service import desktop_intelligence_service


router = APIRouter(prefix="/v1/desktop-intelligence", tags=["desktop-intelligence"])


@router.get("/status", response_model=DesktopIntelligenceStatus)
def desktop_status() -> DesktopIntelligenceStatus:
    return desktop_intelligence_service.status()


@router.post("/sessions", response_model=DesktopSessionRecord, status_code=status.HTTP_201_CREATED)
def create_session(payload: DesktopSessionCreate) -> DesktopSessionRecord:
    try:
        return desktop_intelligence_service.create_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[DesktopSessionRecord])
def list_sessions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DesktopSessionRecord]:
    return desktop_intelligence_service.list_sessions(workspace_id)


@router.get("/sessions/{session_id}", response_model=DesktopSessionRecord)
def get_session(session_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> DesktopSessionRecord:
    item = desktop_intelligence_service.get_session(session_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Desktop session not found")
    return item


def _mutate(session_id: UUID, payload: SessionMutation, workspace_id: str, state: SessionState) -> DesktopSessionRecord:
    item = desktop_intelligence_service.mutate_session(session_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned desktop session not found")
    return item


@router.post("/sessions/{session_id}/activate", response_model=DesktopSessionRecord)
def activate_session(session_id: UUID, payload: SessionMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> DesktopSessionRecord:
    return _mutate(session_id, payload, workspace_id, SessionState.ACTIVE)


@router.post("/sessions/{session_id}/pause", response_model=DesktopSessionRecord)
def pause_session(session_id: UUID, payload: SessionMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> DesktopSessionRecord:
    return _mutate(session_id, payload, workspace_id, SessionState.PAUSED)


@router.post("/sessions/{session_id}/cancel", response_model=DesktopSessionRecord)
def cancel_session(session_id: UUID, payload: SessionMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> DesktopSessionRecord:
    return _mutate(session_id, payload, workspace_id, SessionState.CANCELLED)


@router.post("/snapshots", response_model=DesktopSnapshotRecord, status_code=status.HTTP_201_CREATED)
def add_snapshot(payload: DesktopSnapshotCreate) -> DesktopSnapshotRecord:
    try:
        return desktop_intelligence_service.add_snapshot(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/snapshots", response_model=list[DesktopSnapshotRecord])
def list_snapshots(workspace_id: str = Query(min_length=1, max_length=120), session_id: UUID | None = None) -> list[DesktopSnapshotRecord]:
    return desktop_intelligence_service.list_snapshots(workspace_id, session_id)


@router.post("/actions", response_model=DesktopActionRecord, status_code=status.HTTP_201_CREATED)
def plan_action(payload: DesktopActionCreate) -> DesktopActionRecord:
    try:
        return desktop_intelligence_service.plan_action(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/actions", response_model=list[DesktopActionRecord])
def list_actions(workspace_id: str = Query(min_length=1, max_length=120), session_id: UUID | None = None) -> list[DesktopActionRecord]:
    return desktop_intelligence_service.list_actions(workspace_id, session_id)


@router.post("/actions/{action_id}/approval", response_model=DesktopActionRecord)
def approve_action(action_id: UUID, payload: ApprovalRequest, workspace_id: str = Query(min_length=1, max_length=120)) -> DesktopActionRecord:
    item = desktop_intelligence_service.approve_action(action_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Approvable owned desktop action not found")
    return item


@router.get("/audit", response_model=list[DesktopAuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DesktopAuditRecord]:
    return desktop_intelligence_service.list_audit(workspace_id)
