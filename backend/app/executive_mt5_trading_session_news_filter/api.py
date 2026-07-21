from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, SessionNewsAssessment, SessionNewsAssessmentCreate, SessionNewsExecuteRequest, SessionNewsStatus
from .service import trading_session_news_filter_service

router = APIRouter(tags=["executive-mt5-trading-session-news-filter"])


@router.get("/v1/executive-mt5-trading-session-news-filter/status", response_model=SessionNewsStatus)
def get_status(workspace_id: str = Query(min_length=1, max_length=100)) -> SessionNewsStatus:
    return trading_session_news_filter_service.status(workspace_id)


@router.post("/v1/executive-mt5-trading-session-news-filter/assessments", response_model=SessionNewsAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: SessionNewsAssessmentCreate) -> SessionNewsAssessment:
    try:
        return trading_session_news_filter_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-trading-session-news-filter/assessments", response_model=list[SessionNewsAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[SessionNewsAssessment]:
    return trading_session_news_filter_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-trading-session-news-filter/assessments/{record_id}", response_model=SessionNewsAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> SessionNewsAssessment:
    record = trading_session_news_filter_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session/news assessment not found")
    return record


@router.post("/v1/executive-mt5-trading-session-news-filter/assessments/{record_id}/execute", response_model=SessionNewsAssessment)
def execute_assessment(record_id: UUID, request: SessionNewsExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> SessionNewsAssessment:
    try:
        return trading_session_news_filter_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-trading-session-news-filter/audit", response_model=list[AuditRecord])
def get_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return trading_session_news_filter_service.audit_records(workspace_id)
