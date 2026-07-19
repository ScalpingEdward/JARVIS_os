from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    CustomerListResponse,
    CustomerPortfolioCreate,
    CustomerSignalUpdate,
    CustomerStatusResponse,
    ExecutiveCustomerPortfolio,
)
from .service import executive_customer_service
from app.executive_product.api import router as executive_product_router

router = APIRouter(tags=["executive-customer"])


@router.get("/v1/executive-customer/status", response_model=CustomerStatusResponse)
def customer_status(workspace_id: str = Query(min_length=1, max_length=100)) -> CustomerStatusResponse:
    return executive_customer_service.status(workspace_id)


@router.post(
    "/v1/executive-customer/portfolios",
    response_model=ExecutiveCustomerPortfolio,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio(payload: CustomerPortfolioCreate) -> ExecutiveCustomerPortfolio:
    try:
        return executive_customer_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-customer/portfolios", response_model=CustomerListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> CustomerListResponse:
    items = executive_customer_service.list_portfolios(workspace_id)
    return CustomerListResponse(items=items, count=len(items))


@router.get("/v1/executive-customer/portfolios/{portfolio_id}", response_model=ExecutiveCustomerPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCustomerPortfolio:
    item = executive_customer_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive customer portfolio not found")
    return item


@router.post("/v1/executive-customer/portfolios/{portfolio_id}/signals", response_model=ExecutiveCustomerPortfolio)
def update_signal(
    portfolio_id: UUID,
    payload: CustomerSignalUpdate,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveCustomerPortfolio:
    try:
        return executive_customer_service.update_signal(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-customer/portfolios/{portfolio_id}/assess", response_model=ExecutiveCustomerPortfolio)
def assess_portfolio(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
    actor_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveCustomerPortfolio:
    try:
        return executive_customer_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-customer/audit", response_model=list[AuditRecord])
def customer_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_customer_service.audit_records(workspace_id)


router.include_router(executive_product_router)
