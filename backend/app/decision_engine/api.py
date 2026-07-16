from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import DecisionListResponse, DecisionRecord, DecisionRequest, DecisionStatus
from .service import decision_engine_service

router = APIRouter(prefix="/v1/decisions", tags=["decision-engine"])


@router.get("/status", response_model=DecisionStatus)
def decision_status() -> DecisionStatus:
    return decision_engine_service.status()


@router.post("", response_model=DecisionRecord, status_code=status.HTTP_201_CREATED)
def create_decision(payload: DecisionRequest) -> DecisionRecord:
    return decision_engine_service.evaluate(payload)


@router.get("", response_model=DecisionListResponse)
def list_decisions() -> DecisionListResponse:
    items = decision_engine_service.list_all()
    return DecisionListResponse(items=items, count=len(items))


@router.get("/{decision_id}", response_model=DecisionRecord)
def get_decision(decision_id: UUID) -> DecisionRecord:
    record = decision_engine_service.get(decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return record


@router.post("/{decision_id}/approve", response_model=DecisionRecord)
def approve_decision(decision_id: UUID) -> DecisionRecord:
    try:
        record = decision_engine_service.approve(decision_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return record
