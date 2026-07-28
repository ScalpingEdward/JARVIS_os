"""API contract for PHOENIX v21.145 baseline impact simulation governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.baseline_impact_simulation import BaselineImpactSimulationService

router = APIRouter(prefix="/v1/baseline-impact-simulation", tags=["baseline-impact-simulation"])
service = BaselineImpactSimulationService()


class SimulationIn(BaseModel):
    record_id: str
    workspace_id: str
    active_baseline: dict
    scenarios: list[dict] = Field(default_factory=list)
    source_key: str


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.145",
        "status": "active",
        "simulation_only": True,
        "routing_mutation_enabled": False,
        "policy_mutation_enabled": False,
        "execution_enabled": False,
    }


@router.post("/records")
def create_record(payload: SimulationIn) -> dict:
    try:
        return service.simulate(**payload.model_dump()).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [r.__dict__ for r in service.list_records(workspace_id)]


@router.get("/records/{record_id}")
def record(record_id: str) -> dict:
    try:
        return service.get(record_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="preview not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    if payload.action != "approve":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve(record_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
