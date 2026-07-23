from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, PortfolioActionRequest, StrategicPortfolio, StrategicPortfolioCreate
from .service import StrategicPortfolioError, service

router = APIRouter(prefix="/v1/strategic-portfolio", tags=["PHOENIX v21.41 Strategic Portfolio Coordination"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "strategic-portfolio-coordination", "version": "21.41", "status": "ready"}


@router.post("/portfolios", response_model=StrategicPortfolio)
def create_portfolio(payload: StrategicPortfolioCreate) -> StrategicPortfolio:
    try:
        return service.create(payload)
    except StrategicPortfolioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/portfolios", response_model=list[StrategicPortfolio])
def list_portfolios(x_workspace_id: str = Header(...)) -> list[StrategicPortfolio]:
    return service.list(x_workspace_id)


@router.get("/portfolios/{record_id}", response_model=StrategicPortfolio)
def get_portfolio(record_id: str, x_workspace_id: str = Header(...)) -> StrategicPortfolio:
    try:
        return service.get(record_id, x_workspace_id)
    except StrategicPortfolioError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/portfolios/{record_id}/actions", response_model=StrategicPortfolio)
def act_on_portfolio(record_id: str, request: PortfolioActionRequest, x_workspace_id: str = Header(...)) -> StrategicPortfolio:
    try:
        return service.act(record_id, x_workspace_id, request)
    except StrategicPortfolioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
