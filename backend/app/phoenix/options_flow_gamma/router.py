from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .models import OptionObservation
from .service import OptionsFlowGovernanceError, OptionsFlowGovernanceService

router = APIRouter(prefix="/v1/options-flow-gamma", tags=["options-flow-gamma"])
service = OptionsFlowGovernanceService()


class ObservationPayload(BaseModel):
    source_key: str
    underlying: str
    expiry: str
    strike: float
    option_type: str
    side: str
    premium: float = Field(ge=0)
    contracts: int = Field(ge=0)
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    implied_volatility: float = Field(default=0.0, ge=0)
    open_interest: int = Field(default=0, ge=0)
    volume: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.5, ge=0, le=1)
    freshness: float = Field(default=1.0, ge=0, le=1)
    provenance: str = "unknown"


class CreateRecordPayload(BaseModel):
    observations: list[ObservationPayload]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionPayload(BaseModel):
    action: str
    operation_id: str
    risk_brain_blocked: bool = False


def _workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header is required")
    return value


@router.get("/status")
def status() -> dict[str, Any]:
    return service.status()


@router.post("/records")
def create_record(payload: CreateRecordPayload, x_workspace_id: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        record = service.create_record(
            _workspace(x_workspace_id),
            [OptionObservation(**item.model_dump()) for item in payload.observations],
            payload.metadata,
        )
        return asdict(record)
    except OptionsFlowGovernanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/records")
def list_records(x_workspace_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
    return [asdict(record) for record in service.list_records(_workspace(x_workspace_id))]


@router.get("/records/{record_id}")
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return asdict(service.get_record(_workspace(x_workspace_id), record_id))
    except OptionsFlowGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions")
def apply_action(
    record_id: str,
    payload: ActionPayload,
    x_workspace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        record = service.apply_action(
            _workspace(x_workspace_id),
            record_id,
            payload.action,
            payload.operation_id,
            payload.risk_brain_blocked,
        )
        return asdict(record)
    except OptionsFlowGovernanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
    return service.audit(_workspace(x_workspace_id))
