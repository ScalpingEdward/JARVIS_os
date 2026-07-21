from fastapi import APIRouter, Header, HTTPException, status

from .models import InvestmentDecisionCreate, InvestmentDecisionExecute, InvestmentDecisionRecord
from .service import InvestmentDecisionError, service

router = APIRouter(prefix="/v1/investment-decisions", tags=["investment-decisions"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status")
def get_status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=InvestmentDecisionRecord, status_code=status.HTTP_201_CREATED)
def create_record(payload: InvestmentDecisionCreate, x_workspace_id: str | None = Header(default=None)) -> InvestmentDecisionRecord:
    workspace = _workspace(x_workspace_id)
    if payload.workspace_id != workspace:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="workspace mismatch")
    try:
        return service.create(payload)
    except InvestmentDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/records", response_model=list[InvestmentDecisionRecord])
def list_records(x_workspace_id: str | None = Header(default=None)) -> list[InvestmentDecisionRecord]:
    return service.list(_workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=InvestmentDecisionRecord)
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None)) -> InvestmentDecisionRecord:
    try:
        return service.get(_workspace(x_workspace_id), record_id)
    except InvestmentDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=InvestmentDecisionRecord)
def execute_record(record_id: str, command: InvestmentDecisionExecute, x_workspace_id: str | None = Header(default=None)) -> InvestmentDecisionRecord:
    try:
        return service.execute(_workspace(x_workspace_id), record_id, command)
    except InvestmentDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/audit")
def get_audit(x_workspace_id: str | None = Header(default=None)) -> list[dict[str, object]]:
    return [event.model_dump(mode="json") for event in service.audit(_workspace(x_workspace_id))]
