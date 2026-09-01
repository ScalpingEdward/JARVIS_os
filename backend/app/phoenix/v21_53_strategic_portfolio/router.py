from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, PortfolioActionRequest, StrategicPortfolioCreate, StrategicPortfolioRecord
from .service import StrategicPortfolioError, service

router = APIRouter(
    prefix="/v1/phoenix/strategic-portfolio",
    tags=["PHOENIX v21.53 Strategic Portfolio Orchestration Governance"],
)


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "module": "strategic-portfolio-orchestration-governance",
        "version": "21.53",
        "status": "ready",
    }


@router.post("/records", response_model=StrategicPortfolioRecord)
def create_record(payload: StrategicPortfolioCreate) -> StrategicPortfolioRecord:
    try:
        return service.create(payload)
    except StrategicPortfolioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[StrategicPortfolioRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[StrategicPortfolioRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=StrategicPortfolioRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> StrategicPortfolioRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except StrategicPortfolioError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=StrategicPortfolioRecord)
def act_on_record(
    record_id: str,
    request: PortfolioActionRequest,
    x_workspace_id: str = Header(...),
) -> StrategicPortfolioRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except StrategicPortfolioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
