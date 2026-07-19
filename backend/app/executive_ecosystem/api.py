from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, EcosystemListResponse, EcosystemPortfolioCreate, EcosystemStatusResponse, ExecutiveEcosystemPortfolio, PartnershipUpdate
from .service import executive_ecosystem_service
from app.executive_data_ai.api import router as executive_data_ai_router

router = APIRouter(tags=["executive-ecosystem"])


@router.get("/v1/executive-ecosystem/status", response_model=EcosystemStatusResponse)
def ecosystem_status(workspace_id: str = Query(min_length=1, max_length=100)) -> EcosystemStatusResponse:
    return executive_ecosystem_service.status(workspace_id)


@router.post("/v1/executive-ecosystem/portfolios", response_model=ExecutiveEcosystemPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: EcosystemPortfolioCreate) -> ExecutiveEcosystemPortfolio:
    try:
        return executive_ecosystem_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-ecosystem/portfolios", response_model=EcosystemListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> EcosystemListResponse:
    items = executive_ecosystem_service.list_portfolios(workspace_id)
    return EcosystemListResponse(items=items, count=len(items))


@router.get("/v1/executive-ecosystem/portfolios/{portfolio_id}", response_model=ExecutiveEcosystemPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveEcosystemPortfolio:
    item = executive_ecosystem_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive ecosystem portfolio not found")
    return item


@router.post("/v1/executive-ecosystem/portfolios/{portfolio_id}/partners", response_model=ExecutiveEcosystemPortfolio)
def update_partner(portfolio_id: UUID, payload: PartnershipUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveEcosystemPortfolio:
    try:
        return executive_ecosystem_service.update_partner(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-ecosystem/portfolios/{portfolio_id}/assess", response_model=ExecutiveEcosystemPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveEcosystemPortfolio:
    try:
        return executive_ecosystem_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-ecosystem/audit", response_model=list[AuditRecord])
def ecosystem_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_ecosystem_service.audit_records(workspace_id)


router.include_router(executive_data_ai_router)
