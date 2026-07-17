from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ReplayReport, ReplaySession, ReplaySessionCreate, ReplayStatus, ReplayStepRequest
from .service import market_replay_service


router = APIRouter(prefix="/v1/market-replay", tags=["market-replay"])


@router.get("/status", response_model=ReplayStatus)
def replay_status() -> ReplayStatus:
    return market_replay_service.status()


@router.post("/sessions", response_model=ReplaySession, status_code=status.HTTP_201_CREATED)
def create_session(payload: ReplaySessionCreate) -> ReplaySession:
    return market_replay_service.create(payload)


@router.get("/sessions", response_model=list[ReplaySession])
def list_sessions() -> list[ReplaySession]:
    return market_replay_service.list_all()


@router.get("/sessions/{session_id}", response_model=ReplaySession)
def get_session(session_id: UUID) -> ReplaySession:
    session = market_replay_service.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return session


@router.post("/sessions/{session_id}/step", response_model=ReplaySession)
def step_session(session_id: UUID, payload: ReplayStepRequest) -> ReplaySession:
    session = market_replay_service.step(session_id, payload.bars)
    if session is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return session


@router.post("/sessions/{session_id}/pause", response_model=ReplaySession)
def pause_session(session_id: UUID) -> ReplaySession:
    session = market_replay_service.pause(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return session


@router.post("/sessions/{session_id}/resume", response_model=ReplaySession)
def resume_session(session_id: UUID) -> ReplaySession:
    session = market_replay_service.resume(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return session


@router.post("/sessions/{session_id}/cancel", response_model=ReplaySession)
def cancel_session(session_id: UUID) -> ReplaySession:
    session = market_replay_service.cancel(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return session


@router.get("/sessions/{session_id}/report", response_model=ReplayReport)
def replay_report(session_id: UUID) -> ReplayReport:
    report = market_replay_service.report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return report
