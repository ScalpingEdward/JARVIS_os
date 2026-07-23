from fastapi import APIRouter, Header, HTTPException, status

from app.schemas.real_time_portfolio_ai_brain import (
    PortfolioBrainAction,
    PortfolioBrainCreate,
    PortfolioBrainRecord,
)
from app.services.real_time_portfolio_ai_brain import (
    PortfolioBrainError,
    real_time_portfolio_ai_brain_service,
)

router = APIRouter(prefix="/v1/portfolio-ai-brain", tags=["portfolio-ai-brain"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-Id is required")
    return x_workspace_id


@router.get("/status")
def status_view() -> dict:
    return {
        "module": "PHOENIX v21.77 Real-Time Portfolio AI Brain",
        "mode": "advisory-governance-only",
        "portfolio_mutation_enabled": False,
        "allocation_mutation_enabled": False,
        "routing_mutation_enabled": False,
        "execution_enabled": False,
        "human_approval_required": True,
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=PortfolioBrainRecord, status_code=status.HTTP_201_CREATED)
def create_record(payload: PortfolioBrainCreate) -> PortfolioBrainRecord:
    try:
        return real_time_portfolio_ai_brain_service.create(payload)
    except PortfolioBrainError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/records", response_model=list[PortfolioBrainRecord])
def list_records(x_workspace_id: str | None = Header(default=None)) -> list[PortfolioBrainRecord]:
    return real_time_portfolio_ai_brain_service.list(_workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=PortfolioBrainRecord)
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None)) -> PortfolioBrainRecord:
    try:
        return real_time_portfolio_ai_brain_service.get(_workspace(x_workspace_id), record_id)
    except PortfolioBrainError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=PortfolioBrainRecord)
def act_on_record(record_id: str, command: PortfolioBrainAction, x_workspace_id: str | None = Header(default=None)) -> PortfolioBrainRecord:
    try:
        return real_time_portfolio_ai_brain_service.act(_workspace(x_workspace_id), record_id, command)
    except PortfolioBrainError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/audit")
def audit_view(x_workspace_id: str | None = Header(default=None)) -> list[dict]:
    return real_time_portfolio_ai_brain_service.audit(_workspace(x_workspace_id))
