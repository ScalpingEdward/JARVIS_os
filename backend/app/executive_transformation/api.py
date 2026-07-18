from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveTransformationPortfolio, ProgressUpdate, TransformationListResponse, TransformationPortfolioCreate, TransformationStatusResponse
from .service import executive_transformation_service

router = APIRouter(tags=["executive-transformation"])


@router.get("/v1/executive-transformation/status", response_model=TransformationStatusResponse)
def transformation_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TransformationStatusResponse:
    return executive_transformation_service.status(workspace_id)


@router.post("/v1/executive-transformation/portfolios", response_model=ExecutiveTransformationPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: TransformationPortfolioCreate) -> ExecutiveTransformationPortfolio:
    try:
        return executive_transformation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-transformation/portfolios", response_model=TransformationListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> TransformationListResponse:
    items = executive_transformation_service.list_portfolios(workspace_id)
    return TransformationListResponse(items=items, count=len(items))


@router.get("/v1/executive-transformation/portfolios/{portfolio_id}", response_model=ExecutiveTransformationPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTransformationPortfolio:
    record = executive_transformation_service.get(portfolio_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive transformation portfolio not found")
    return record


@router.post("/v1/executive-transformation/portfolios/{portfolio_id}/progress", response_model=ExecutiveTransformationPortfolio)
def update_progress(portfolio_id: UUID, payload: ProgressUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTransformationPortfolio:
    try:
        return executive_transformation_service.update_progress(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-transformation/portfolios/{portfolio_id}/assess", response_model=ExecutiveTransformationPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTransformationPortfolio:
    try:
        return executive_transformation_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-transformation/audit", response_model=list[AuditRecord])
def transformation_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_transformation_service.audit_records(workspace_id)
