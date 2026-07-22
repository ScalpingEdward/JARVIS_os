from fastapi import APIRouter, Header, HTTPException

from .schemas import ExposureDecision, ExposureExecutionRequest, PortfolioExposureRequest
from .service import PortfolioExposureError, service

router = APIRouter(prefix="/v1/portfolio-exposure", tags=["portfolio-exposure"])


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.18 Portfolio Exposure Manager",
        "status": "ready",
        "live_execution": False,
        "human_approval_required": True,
    }


@router.post("/records", response_model=ExposureDecision)
def create_record(payload: PortfolioExposureRequest) -> ExposureDecision:
    try:
        return service.assess(payload)
    except PortfolioExposureError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ExposureDecision])
def list_records(x_workspace_id: str = Header(...)) -> list[ExposureDecision]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=ExposureDecision)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> ExposureDecision:
    try:
        return service.get(x_workspace_id, record_id)
    except PortfolioExposureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=ExposureDecision)
def execute_record(
    record_id: str,
    command: ExposureExecutionRequest,
    x_workspace_id: str = Header(...),
) -> ExposureDecision:
    try:
        return service.execute(x_workspace_id, record_id, command)
    except PortfolioExposureError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str = Header(...)) -> list[dict]:
    return service.audit(x_workspace_id)
