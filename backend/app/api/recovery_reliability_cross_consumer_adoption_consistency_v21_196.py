"""API surface for PHOENIX v21.196 recovery reliability adoption consistency governance."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.recovery_reliability_cross_consumer_adoption_consistency_v21_196 import (
    AdoptionObservation,
    CrossConsumerAdoptionRecord,
    RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance,
)

router = APIRouter(prefix="/v1/recovery-reliability-adoption-consistency", tags=["recovery-reliability-adoption-consistency-v21.196"])
governance = RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance()


class ObservationIn(BaseModel):
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    receipt_nonce: str
    receipt_age_seconds: int
    healthy: bool
    adopted: bool
    confidence: float


class RecordIn(BaseModel):
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    expected_consumers: list[str]
    observations: list[ObservationIn]
    receipt_ttl_seconds: int = 900
    min_consistency_score: float = 0.95
    risk_brain_blocked: bool = False
    source_state: str
    source_human_approved: bool


class ApprovalIn(BaseModel):
    actor: str
    human_approved: bool


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.196",
        "runtime_mutation_enabled": False,
        "baseline_mutation_enabled": False,
        "execution_enabled": False,
        "device_actuation_enabled": False,
    }


@router.post("/records")
def create_record(payload: RecordIn) -> dict:
    record = CrossConsumerAdoptionRecord(
        record_id=payload.record_id,
        workspace_id=payload.workspace_id,
        source_record_id=payload.source_record_id,
        baseline_id=payload.baseline_id,
        baseline_version=payload.baseline_version,
        baseline_digest=payload.baseline_digest,
        expected_consumers=tuple(payload.expected_consumers),
        observations=tuple(AdoptionObservation(**o.model_dump()) for o in payload.observations),
        receipt_ttl_seconds=payload.receipt_ttl_seconds,
        min_consistency_score=payload.min_consistency_score,
        risk_brain_blocked=payload.risk_brain_blocked,
    )
    return governance.observe(
        record,
        source_state=payload.source_state,
        source_human_approved=payload.source_human_approved,
    ).snapshot()


@router.get("/records")
def list_records() -> list[dict]:
    return [r.snapshot() for r in governance.records.values()]


@router.get("/records/{record_id}")
def get_record(record_id: str) -> dict:
    if record_id not in governance.records:
        raise HTTPException(status_code=404, detail="record not found")
    return governance.records[record_id].snapshot()


@router.post("/records/{record_id}/approve-consistency")
def approve_consistency(record_id: str, payload: ApprovalIn) -> dict:
    if record_id not in governance.records:
        raise HTTPException(status_code=404, detail="record not found")
    return governance.approve_consistency(
        record_id,
        actor=payload.actor,
        human_approved=payload.human_approved,
    ).snapshot()


@router.get("/audit")
def audit() -> list[dict]:
    return list(governance.audit)
