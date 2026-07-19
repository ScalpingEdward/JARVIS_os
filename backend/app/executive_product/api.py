from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveProductPortfolio, InitiativeUpdate, ProductListResponse, ProductPortfolioCreate, ProductStatusResponse
from .service import executive_product_service
from app.executive_ecosystem.api import router as executive_ecosystem_router

router = APIRouter(tags=["executive-product"])


@router.get("/v1/executive-product/status", response_model=ProductStatusResponse)
def product_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ProductStatusResponse:
    return executive_product_service.status(workspace_id)


@router.post("/v1/executive-product/portfolios", response_model=ExecutiveProductPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: ProductPortfolioCreate) -> ExecutiveProductPortfolio:
    try:
        return executive_product_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-product/portfolios", response_model=ProductListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> ProductListResponse:
    items = executive_product_service.list_portfolios(workspace_id)
    return ProductListResponse(items=items, count=len(items))


@router.get("/v1/executive-product/portfolios/{portfolio_id}", response_model=ExecutiveProductPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveProductPortfolio:
    item = executive_product_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive product portfolio not found")
    return item


@router.post("/v1/executive-product/portfolios/{portfolio_id}/initiatives", response_model=ExecutiveProductPortfolio)
def update_initiative(portfolio_id: UUID, payload: InitiativeUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveProductPortfolio:
    try:
        return executive_product_service.update_initiative(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-product/portfolios/{portfolio_id}/assess", response_model=ExecutiveProductPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveProductPortfolio:
    try:
        return executive_product_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-product/audit", response_model=list[AuditRecord])
def product_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_product_service.audit_records(workspace_id)


router.include_router(executive_ecosystem_router)
