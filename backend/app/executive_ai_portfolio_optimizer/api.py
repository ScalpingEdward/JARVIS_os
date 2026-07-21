from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from .models import (
    PortfolioOptimizerAudit,
    PortfolioOptimizerCreate,
    PortfolioOptimizerExecuteRequest,
    PortfolioOptimizerRecord,
    PortfolioOptimizerStatus,
)
from .service import ai_portfolio_optimizer_service

router = APIRouter(prefix="/v1/executive-ai-portfolio-optimizer", tags=["executive-ai-portfolio-optimizer"])


@router.get("/status", response_model=PortfolioOptimizerStatus)
def status(workspace_id: str = Query(min_length=1)):
    return ai_portfolio_optimizer_service.status(workspace_id)


@router.post("/optimizations", response_model=PortfolioOptimizerRecord)
def create_optimization(payload: PortfolioOptimizerCreate):
    try:
        return ai_portfolio_optimizer_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/optimizations", response_model=list[PortfolioOptimizerRecord])
def list_optimizations(workspace_id: str = Query(min_length=1)):
    return ai_portfolio_optimizer_service.list_records(workspace_id)


@router.get("/optimizations/{record_id}", response_model=PortfolioOptimizerRecord)
def get_optimization(record_id: UUID, workspace_id: str = Query(min_length=1)):
    record = ai_portfolio_optimizer_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="optimizer record not found")
    return record


@router.post("/optimizations/{record_id}/execute", response_model=PortfolioOptimizerRecord)
def execute_optimization(
    record_id: UUID,
    request: PortfolioOptimizerExecuteRequest,
    workspace_id: str = Header(alias="X-Workspace-ID", min_length=1),
):
    try:
        return ai_portfolio_optimizer_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[PortfolioOptimizerAudit])
def audit(workspace_id: str = Query(min_length=1)):
    return ai_portfolio_optimizer_service.audit_records(workspace_id)
