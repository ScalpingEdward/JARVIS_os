from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..executive_order_flow.api import router as executive_order_flow_router
from .models import AuditRecord, ExecutiveRemoteWorkPortfolio, RemoteWorkListResponse, RemoteWorkPortfolioCreate, RemoteWorkRiskUpdate, RemoteWorkStatusResponse
from .service import executive_remote_work_service

router = APIRouter(tags=["executive-remote-work"])
router.include_router(executive_order_flow_router)


@router.get("/v1/executive-remote-work/status", response_model=RemoteWorkStatusResponse)
def remote_work_status(workspace_id: str = Query(min_length=1, max_length=100)) -> RemoteWorkStatusResponse:
    return executive_remote_work_service.status(workspace_id)


@router.post("/v1/executive-remote-work/portfolios", response_model=ExecutiveRemoteWorkPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: RemoteWorkPortfolioCreate) -> ExecutiveRemoteWorkPortfolio:
    try:
        return executive_remote_work_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-remote-work/portfolios", response_model=RemoteWorkListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> RemoteWorkListResponse:
    items = executive_remote_work_service.list_portfolios(workspace_id)
    return RemoteWorkListResponse(items=items, count=len(items))


@router.get("/v1/executive-remote-work/portfolios/{portfolio_id}", response_model=ExecutiveRemoteWorkPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveRemoteWorkPortfolio:
    item = executive_remote_work_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive remote-work portfolio not found")
    return item


@router.post("/v1/executive-remote-work/portfolios/{portfolio_id}/risks", response_model=ExecutiveRemoteWorkPortfolio)
def update_risk(portfolio_id: UUID, payload: RemoteWorkRiskUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveRemoteWorkPortfolio:
    try:
        return executive_remote_work_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-remote-work/portfolios/{portfolio_id}/assess", response_model=ExecutiveRemoteWorkPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveRemoteWorkPortfolio:
    try:
        return executive_remote_work_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-remote-work/audit", response_model=list[AuditRecord])
def remote_work_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_remote_work_service.audit_records(workspace_id)
