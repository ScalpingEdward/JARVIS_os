from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, DataAIListResponse, DataAIPortfolioCreate, DataAIStatusResponse, ExecutiveDataAIPortfolio, GovernanceUpdate
from .service import executive_data_ai_service
from app.executive_esg.api import router as executive_esg_router

router = APIRouter(tags=["executive-data-ai"])


@router.get("/v1/executive-data-ai/status", response_model=DataAIStatusResponse)
def data_ai_status(workspace_id: str = Query(min_length=1, max_length=100)) -> DataAIStatusResponse:
    return executive_data_ai_service.status(workspace_id)


@router.post("/v1/executive-data-ai/portfolios", response_model=ExecutiveDataAIPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: DataAIPortfolioCreate) -> ExecutiveDataAIPortfolio:
    try:
        return executive_data_ai_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-data-ai/portfolios", response_model=DataAIListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> DataAIListResponse:
    items = executive_data_ai_service.list_portfolios(workspace_id)
    return DataAIListResponse(items=items, count=len(items))


@router.get("/v1/executive-data-ai/portfolios/{portfolio_id}", response_model=ExecutiveDataAIPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDataAIPortfolio:
    item = executive_data_ai_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive data AI portfolio not found")
    return item


@router.post("/v1/executive-data-ai/portfolios/{portfolio_id}/issues", response_model=ExecutiveDataAIPortfolio)
def update_issue(portfolio_id: UUID, payload: GovernanceUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDataAIPortfolio:
    try:
        return executive_data_ai_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-data-ai/portfolios/{portfolio_id}/assess", response_model=ExecutiveDataAIPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDataAIPortfolio:
    try:
        return executive_data_ai_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-data-ai/audit", response_model=list[AuditRecord])
def data_ai_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_data_ai_service.audit_records(workspace_id)


router.include_router(executive_esg_router)
