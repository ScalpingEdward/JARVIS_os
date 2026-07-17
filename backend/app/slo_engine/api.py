from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    EvaluationRecord, MeasurementCreate, MeasurementRecord, MetricsRecord,
    Mutation, SLOCreate, SLORecord, SLOState, SLOStatus,
)
from .service import slo_service as service

router = APIRouter(prefix="/v1/slo", tags=["slo"])


@router.get("/status", response_model=SLOStatus)
def get_status() -> SLOStatus:
    return service.status()


@router.post("/objectives", response_model=SLORecord, status_code=status.HTTP_201_CREATED)
def create_slo(payload: SLOCreate) -> SLORecord:
    try:
        return service.create_slo(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/objectives", response_model=list[SLORecord])
def list_slos(workspace_id: str = Query(min_length=1, max_length=120)) -> list[SLORecord]:
    return service.list_slos(workspace_id)


@router.get("/objectives/{slo_id}", response_model=SLORecord)
def get_slo(slo_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> SLORecord:
    item = service.get_slo(slo_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="SLO not found")
    return item


def _set_slo(slo_id: UUID, workspace_id: str, payload: Mutation, state: SLOState) -> SLORecord:
    item = service.set_state(slo_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned SLO not found")
    return item


@router.post("/objectives/{slo_id}/activate", response_model=SLORecord)
def activate_slo(slo_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> SLORecord:
    return _set_slo(slo_id, workspace_id, payload, SLOState.ACTIVE)


@router.post("/objectives/{slo_id}/pause", response_model=SLORecord)
def pause_slo(slo_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> SLORecord:
    return _set_slo(slo_id, workspace_id, payload, SLOState.PAUSED)


@router.post("/objectives/{slo_id}/retire", response_model=SLORecord)
def retire_slo(slo_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> SLORecord:
    return _set_slo(slo_id, workspace_id, payload, SLOState.RETIRED)


@router.post("/measurements", response_model=dict, status_code=status.HTTP_201_CREATED)
def record_measurement(payload: MeasurementCreate):
    try:
        measurement, evaluation = service.record_measurement(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"measurement": measurement, "evaluation": evaluation}


@router.get("/measurements", response_model=list[MeasurementRecord])
def list_measurements(workspace_id: str = Query(min_length=1, max_length=120), slo_id: UUID | None = None) -> list[MeasurementRecord]:
    return service.list_measurements(workspace_id, slo_id)


@router.get("/evaluations", response_model=list[EvaluationRecord])
def list_evaluations(workspace_id: str = Query(min_length=1, max_length=120), slo_id: UUID | None = None) -> list[EvaluationRecord]:
    return service.list_evaluations(workspace_id, slo_id)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
