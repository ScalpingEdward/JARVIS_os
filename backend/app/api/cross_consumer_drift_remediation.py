"""API for PHOENIX v21.157 cross-consumer drift remediation governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.cross_consumer_drift_remediation import CrossConsumerDriftRemediationService

router = APIRouter(prefix="/v1/cross-consumer-drift-remediation", tags=["cross-consumer-drift-remediation"])
service = CrossConsumerDriftRemediationService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    inconsistent_evidence: dict
    source_key: str
    max_blast_radius: float = 0.60
    max_residual_risk: float = 0.35


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {"module": "v21.157", "status": "active", "execution": False, "autonomous_remediation": False}


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        return service.create(**payload.model_dump()).__dict__
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
        raise HTTPException(status_code=404, detail="record not found") from exc


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
