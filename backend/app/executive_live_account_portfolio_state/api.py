from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AccountPortfolioAudit, AccountPortfolioRefreshRequest, AccountPortfolioSnapshot, AccountPortfolioSnapshotCreate, AccountPortfolioStatus
from .service import live_account_portfolio_state_service

router = APIRouter(tags=["executive-live-account-portfolio-state"])


@router.get("/v1/executive-live-account-state/status", response_model=AccountPortfolioStatus)
def account_state_status(workspace_id: str = Query(min_length=1, max_length=100)) -> AccountPortfolioStatus:
    return live_account_portfolio_state_service.status(workspace_id)


@router.post("/v1/executive-live-account-state/snapshots", response_model=AccountPortfolioSnapshot, status_code=status.HTTP_201_CREATED)
def create_snapshot(payload: AccountPortfolioSnapshotCreate) -> AccountPortfolioSnapshot:
    try:
        return live_account_portfolio_state_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-live-account-state/snapshots", response_model=list[AccountPortfolioSnapshot])
def list_snapshots(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AccountPortfolioSnapshot]:
    return live_account_portfolio_state_service.list_records(workspace_id)


@router.get("/v1/executive-live-account-state/snapshots/{record_id}", response_model=AccountPortfolioSnapshot)
def get_snapshot(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> AccountPortfolioSnapshot:
    record = live_account_portfolio_state_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return record


@router.post("/v1/executive-live-account-state/snapshots/{record_id}/refresh", response_model=AccountPortfolioSnapshot)
def refresh_snapshot(record_id: UUID, request: AccountPortfolioRefreshRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> AccountPortfolioSnapshot:
    try:
        return live_account_portfolio_state_service.refresh(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-live-account-state/audit", response_model=list[AccountPortfolioAudit])
def account_state_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AccountPortfolioAudit]:
    return live_account_portfolio_state_service.audit_records(workspace_id)
