from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, BoardListResponse, BoardPortfolioCreate, BoardStatusResponse, ExecutiveBoardPortfolio, GovernanceIssueUpdate
from .service import executive_board_service

router = APIRouter(tags=["executive-board"])


@router.get("/v1/executive-board/status", response_model=BoardStatusResponse)
def board_status(workspace_id: str = Query(min_length=1, max_length=100)) -> BoardStatusResponse:
    return executive_board_service.status(workspace_id)


@router.post("/v1/executive-board/portfolios", response_model=ExecutiveBoardPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: BoardPortfolioCreate) -> ExecutiveBoardPortfolio:
    try:
        return executive_board_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-board/portfolios", response_model=BoardListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> BoardListResponse:
    items = executive_board_service.list_portfolios(workspace_id)
    return BoardListResponse(items=items, count=len(items))


@router.get("/v1/executive-board/portfolios/{portfolio_id}", response_model=ExecutiveBoardPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveBoardPortfolio:
    item = executive_board_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive board portfolio not found")
    return item


@router.post("/v1/executive-board/portfolios/{portfolio_id}/issues", response_model=ExecutiveBoardPortfolio)
def update_issue(portfolio_id: UUID, payload: GovernanceIssueUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveBoardPortfolio:
    try:
        return executive_board_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-board/portfolios/{portfolio_id}/assess", response_model=ExecutiveBoardPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveBoardPortfolio:
    try:
        return executive_board_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-board/audit", response_model=list[AuditRecord])
def board_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_board_service.audit_records(workspace_id)
