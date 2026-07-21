from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import GovernorExecuteRequest, PortfolioGovernorAudit, PortfolioGovernorCreate, PortfolioGovernorRecord, PortfolioGovernorStatus
from .service import autonomous_portfolio_governor_service

router = APIRouter(prefix="/v1/executive-autonomous-portfolio-governor", tags=["executive-autonomous-portfolio-governor"])


@router.get("/status", response_model=PortfolioGovernorStatus)
def status(workspace_id: str = Query(...)):
    return autonomous_portfolio_governor_service.status(workspace_id)


@router.post("/governance", response_model=PortfolioGovernorRecord)
def create_governance(payload: PortfolioGovernorCreate):
    try:
        return autonomous_portfolio_governor_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/governance", response_model=list[PortfolioGovernorRecord])
def list_governance(workspace_id: str = Query(...)):
    return autonomous_portfolio_governor_service.list_records(workspace_id)


@router.get("/governance/{record_id}", response_model=PortfolioGovernorRecord)
def get_governance(record_id: UUID, workspace_id: str = Query(...)):
    record = autonomous_portfolio_governor_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="governor record not found")
    return record


@router.post("/governance/{record_id}/execute", response_model=PortfolioGovernorRecord)
def execute_governance(record_id: UUID, request: GovernorExecuteRequest, workspace_id: str = Query(...)):
    try:
        return autonomous_portfolio_governor_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[PortfolioGovernorAudit])
def audit(workspace_id: str = Query(...)):
    return autonomous_portfolio_governor_service.audit_records(workspace_id)
