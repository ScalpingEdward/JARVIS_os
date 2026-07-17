from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    BrowserAuditRecord,
    BrowserIntelligenceStatus,
    BrowserSessionCreate,
    BrowserSessionRecord,
    NavigationStepCreate,
    NavigationStepRecord,
    PageAnalysisRecord,
    PageAnalysisRequest,
    PageSnapshotCreate,
    PageSnapshotRecord,
    SessionMutation,
    StepApproval,
)
from .service import browser_intelligence_service


router = APIRouter(prefix="/v1/browser-intelligence", tags=["browser-intelligence"])


@router.get("/status", response_model=BrowserIntelligenceStatus)
def browser_status() -> BrowserIntelligenceStatus:
    return browser_intelligence_service.status()


@router.post("/sessions", response_model=BrowserSessionRecord, status_code=status.HTTP_201_CREATED)
def create_session(payload: BrowserSessionCreate) -> BrowserSessionRecord:
    try:
        return browser_intelligence_service.create_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[BrowserSessionRecord])
def list_sessions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[BrowserSessionRecord]:
    return browser_intelligence_service.list_sessions(workspace_id)


@router.get("/sessions/{session_id}", response_model=BrowserSessionRecord)
def get_session(session_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> BrowserSessionRecord:
    session = browser_intelligence_service.get_session(session_id, workspace_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Browser session not found")
    return session


@router.post("/sessions/{session_id}/activate", response_model=BrowserSessionRecord)
def activate_session(
    session_id: UUID,
    payload: SessionMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> BrowserSessionRecord:
    session = browser_intelligence_service.activate_session(session_id, workspace_id, payload)
    if session is None:
        raise HTTPException(status_code=404, detail="Owned browser session not found")
    return session


@router.post("/sessions/{session_id}/pause", response_model=BrowserSessionRecord)
def pause_session(
    session_id: UUID,
    payload: SessionMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> BrowserSessionRecord:
    session = browser_intelligence_service.pause_session(session_id, workspace_id, payload)
    if session is None:
        raise HTTPException(status_code=404, detail="Active owned browser session not found")
    return session


@router.post("/sessions/{session_id}/cancel", response_model=BrowserSessionRecord)
def cancel_session(
    session_id: UUID,
    payload: SessionMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> BrowserSessionRecord:
    session = browser_intelligence_service.cancel_session(session_id, workspace_id, payload)
    if session is None:
        raise HTTPException(status_code=404, detail="Cancellable owned browser session not found")
    return session


@router.post("/snapshots", response_model=PageSnapshotRecord, status_code=status.HTTP_201_CREATED)
def add_snapshot(payload: PageSnapshotCreate) -> PageSnapshotRecord:
    try:
        return browser_intelligence_service.add_snapshot(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/snapshots", response_model=list[PageSnapshotRecord])
def list_snapshots(
    workspace_id: str = Query(min_length=1, max_length=120),
    session_id: UUID | None = Query(default=None),
) -> list[PageSnapshotRecord]:
    return browser_intelligence_service.list_snapshots(workspace_id, session_id)


@router.post("/steps", response_model=NavigationStepRecord, status_code=status.HTTP_201_CREATED)
def plan_step(payload: NavigationStepCreate) -> NavigationStepRecord:
    try:
        return browser_intelligence_service.plan_step(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/steps", response_model=list[NavigationStepRecord])
def list_steps(
    workspace_id: str = Query(min_length=1, max_length=120),
    session_id: UUID | None = Query(default=None),
) -> list[NavigationStepRecord]:
    return browser_intelligence_service.list_steps(workspace_id, session_id)


@router.post("/steps/{step_id}/approval", response_model=NavigationStepRecord)
def approve_step(
    step_id: UUID,
    payload: StepApproval,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> NavigationStepRecord:
    step = browser_intelligence_service.approve_step(step_id, workspace_id, payload)
    if step is None:
        raise HTTPException(status_code=404, detail="Approvable owned browser step not found")
    return step


@router.post("/analyses", response_model=PageAnalysisRecord, status_code=status.HTTP_201_CREATED)
def analyze_page(payload: PageAnalysisRequest) -> PageAnalysisRecord:
    try:
        return browser_intelligence_service.analyze_page(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/analyses", response_model=list[PageAnalysisRecord])
def list_analyses(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PageAnalysisRecord]:
    return browser_intelligence_service.list_analyses(workspace_id)


@router.get("/audit", response_model=list[BrowserAuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[BrowserAuditRecord]:
    return browser_intelligence_service.list_audit(workspace_id)
