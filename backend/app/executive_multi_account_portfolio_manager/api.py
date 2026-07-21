from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import MultiAccountAllocationCreate, MultiAccountAllocationExecuteRequest, MultiAccountAllocationRecord, MultiAccountPortfolioAudit, MultiAccountPortfolioStatus
from .service import multi_account_portfolio_manager_service

router = APIRouter(tags=["executive-multi-account-portfolio-manager"])


@router.get("/v1/executive-multi-account-portfolio/status", response_model=MultiAccountPortfolioStatus)
def portfolio_status(workspace_id: str = Query(min_length=1, max_length=100)):
    return multi_account_portfolio_manager_service.status(workspace_id)


@router.post("/v1/executive-multi-account-portfolio/allocations", response_model=MultiAccountAllocationRecord, status_code=status.HTTP_201_CREATED)
def create_allocation(payload: MultiAccountAllocationCreate):
    try:
        return multi_account_portfolio_manager_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-multi-account-portfolio/allocations", response_model=list[MultiAccountAllocationRecord])
def list_allocations(workspace_id: str = Query(min_length=1, max_length=100)):
    return multi_account_portfolio_manager_service.list_records(workspace_id)


@router.get("/v1/executive-multi-account-portfolio/allocations/{record_id}", response_model=MultiAccountAllocationRecord)
def get_allocation(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)):
    record = multi_account_portfolio_manager_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="allocation record not found")
    return record


@router.post("/v1/executive-multi-account-portfolio/allocations/{record_id}/execute", response_model=MultiAccountAllocationRecord)
def execute_allocation(record_id: UUID, request: MultiAccountAllocationExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)):
    try:
        return multi_account_portfolio_manager_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-multi-account-portfolio/audit", response_model=list[MultiAccountPortfolioAudit])
def portfolio_audit(workspace_id: str = Query(min_length=1, max_length=100)):
    return multi_account_portfolio_manager_service.audit_records(workspace_id)
