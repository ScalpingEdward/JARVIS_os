from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    CalibrationReport,
    DecisionDomain,
    DecisionMemoryList,
    DecisionMemoryStatus,
    DecisionRecord,
    DecisionRecordCreate,
    PatternList,
)
from .service import decision_memory_service


router = APIRouter(prefix="/v1/decision-memory", tags=["decision-memory"])


@router.get("/status", response_model=DecisionMemoryStatus)
def memory_status() -> DecisionMemoryStatus:
    return decision_memory_service.status()


@router.post("/records", response_model=DecisionRecord, status_code=status.HTTP_201_CREATED)
def create_record(payload: DecisionRecordCreate) -> DecisionRecord:
    return decision_memory_service.add(payload)


@router.get("/records", response_model=DecisionMemoryList)
def list_records(domain: DecisionDomain | None = Query(default=None)) -> DecisionMemoryList:
    items = decision_memory_service.list_all(domain=domain)
    return DecisionMemoryList(items=items, count=len(items))


@router.get("/records/{record_id}", response_model=DecisionRecord)
def get_record(record_id: UUID) -> DecisionRecord:
    record = decision_memory_service.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Decision record not found")
    return record


@router.get("/patterns", response_model=PatternList)
def list_patterns(domain: DecisionDomain | None = Query(default=None)) -> PatternList:
    items = decision_memory_service.patterns(domain=domain)
    return PatternList(items=items, count=len(items))


@router.get("/calibration", response_model=CalibrationReport)
def calibration(domain: DecisionDomain | None = Query(default=None)) -> CalibrationReport:
    return decision_memory_service.calibration(domain=domain)
