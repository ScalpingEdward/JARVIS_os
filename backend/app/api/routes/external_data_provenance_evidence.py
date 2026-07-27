from fastapi import APIRouter, HTTPException, Query

from app.schemas.external_data_provenance_evidence import (
    ExternalEvidenceAction,
    ExternalEvidenceCreate,
    ExternalEvidenceRecord,
)
from app.services.external_data_provenance_evidence import external_data_provenance_evidence_service

router = APIRouter(prefix="/v1/external-data-provenance", tags=["external-data-provenance"])


@router.get("/status")
def status() -> dict:
    return external_data_provenance_evidence_service.status()


@router.post("/records", response_model=ExternalEvidenceRecord)
def create_record(payload: ExternalEvidenceCreate) -> ExternalEvidenceRecord:
    try:
        return external_data_provenance_evidence_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ExternalEvidenceRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ExternalEvidenceRecord]:
    return external_data_provenance_evidence_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ExternalEvidenceRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ExternalEvidenceRecord:
    try:
        return external_data_provenance_evidence_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ExternalEvidenceRecord)
def act(record_id: str, payload: ExternalEvidenceAction) -> ExternalEvidenceRecord:
    try:
        return external_data_provenance_evidence_service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return external_data_provenance_evidence_service.audit(workspace_id)
