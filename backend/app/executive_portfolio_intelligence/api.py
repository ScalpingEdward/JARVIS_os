from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PortfolioRun, PortfolioRunCreate, PortfolioRunList, PortfolioStatus
from .service import executive_portfolio_intelligence_service

router = APIRouter(tags=["executive-portfolio-intelligence"])


@router.get("/v1/executive-portfolio-intelligence/status", response_model=PortfolioStatus)
def portfolio_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PortfolioStatus:
    return executive_portfolio_intelligence_service.status(workspace_id)


@router.post(
    "/v1/executive-portfolio-intelligence/runs",
    response_model=PortfolioRun,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio_run(payload: PortfolioRunCreate) -> PortfolioRun:
    return executive_portfolio_intelligence_service.create_run(payload)


@router.get("/v1/executive-portfolio-intelligence/runs", response_model=PortfolioRunList)
def list_portfolio_runs(
    workspace_id: str = Query(min_length=1, max_length=100),
    account_profile_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> PortfolioRunList:
    items = executive_portfolio_intelligence_service.list_runs(workspace_id, account_profile_id)
    return PortfolioRunList(items=items, count=len(items))


@router.get("/v1/executive-portfolio-intelligence/runs/{run_id}", response_model=PortfolioRun)
def get_portfolio_run(
    run_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> PortfolioRun:
    item = executive_portfolio_intelligence_service.get_run(run_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive portfolio run not found")
    return item


@router.get("/v1/executive-portfolio-intelligence/audit", response_model=list[AuditRecord])
def portfolio_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_portfolio_intelligence_service.audit_records(workspace_id)
