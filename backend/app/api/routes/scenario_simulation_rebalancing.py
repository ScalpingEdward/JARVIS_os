from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.scenario_simulation_rebalancing import (
    ScenarioAction,
    ScenarioRecord,
    ScenarioRecordCreate,
)
from app.services.scenario_simulation_rebalancing import scenario_simulation_service

router = APIRouter(prefix="/v1/scenario-simulation", tags=["scenario-simulation"])


@router.get("/status")
def status() -> dict:
    return scenario_simulation_service.status()


@router.post("/records", response_model=ScenarioRecord)
def create_record(payload: ScenarioRecordCreate) -> ScenarioRecord:
    try:
        return scenario_simulation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ScenarioRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ScenarioRecord]:
    return scenario_simulation_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ScenarioRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ScenarioRecord:
    try:
        return scenario_simulation_service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ScenarioRecord)
def apply_action(
    record_id: str,
    payload: ScenarioAction,
    workspace_id: str = Query(min_length=1),
    x_risk_brain_blocked: bool = Header(default=False),
) -> ScenarioRecord:
    try:
        return scenario_simulation_service.act(record_id, workspace_id, payload, x_risk_brain_blocked)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return scenario_simulation_service.audit(workspace_id)
