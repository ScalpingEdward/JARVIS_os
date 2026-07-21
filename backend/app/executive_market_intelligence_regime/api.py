from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    MarketIntelligenceAudit,
    MarketIntelligenceCreate,
    MarketIntelligenceExecuteRequest,
    MarketIntelligenceRecord,
    MarketIntelligenceStatus,
)
from .service import market_intelligence_regime_service

router = APIRouter(tags=["executive-market-intelligence-regime"])


@router.get("/v1/executive-market-intelligence/status", response_model=MarketIntelligenceStatus)
def market_status(workspace_id: str = Query(min_length=1, max_length=100)):
    return market_intelligence_regime_service.status(workspace_id)


@router.post("/v1/executive-market-intelligence/assessments", response_model=MarketIntelligenceRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: MarketIntelligenceCreate):
    try:
        return market_intelligence_regime_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-market-intelligence/assessments", response_model=list[MarketIntelligenceRecord])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)):
    return market_intelligence_regime_service.list_records(workspace_id)


@router.get("/v1/executive-market-intelligence/assessments/{record_id}", response_model=MarketIntelligenceRecord)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)):
    record = market_intelligence_regime_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="market intelligence record not found")
    return record


@router.post("/v1/executive-market-intelligence/assessments/{record_id}/execute", response_model=MarketIntelligenceRecord)
def execute_assessment(record_id: UUID, request: MarketIntelligenceExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)):
    try:
        return market_intelligence_regime_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-market-intelligence/audit", response_model=list[MarketIntelligenceAudit])
def market_audit(workspace_id: str = Query(min_length=1, max_length=100)):
    return market_intelligence_regime_service.audit_records(workspace_id)
