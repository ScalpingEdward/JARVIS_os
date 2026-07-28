"""API contract for PHOENIX v21.148 consumer quarantine governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.baseline_consumer_quarantine import BaselineConsumerQuarantineService

router = APIRouter(prefix="/v1/baseline-consumer-quarantine", tags=["baseline-consumer-quarantine"])
service = BaselineConsumerQuarantineService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    drift_receipt: dict
    source_key: str


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False
    receipt: dict | None = None


@router.get("/status")
def status() -> dict:
    return {"module": "v21.148", "status": "active", "execution": False, "autonomous_correction": False}


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        return service.create_from_drift(**payload.model_dump()).__dict__
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
    try:
        if payload.action == "quarantine":
            return service.quarantine(record_id, human_approved=payload.human_approved).__dict__
        if payload.action == "submit-readoption":
            if payload.receipt is None:
                raise ValueError("receipt required")
            return service.submit_readoption(record_id, receipt=payload.receipt).__dict__
        if payload.action == "approve-readoption":
            return service.approve_readoption(record_id, human_approved=payload.human_approved).__dict__
        raise HTTPException(status_code=400, detail="unsupported action")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
