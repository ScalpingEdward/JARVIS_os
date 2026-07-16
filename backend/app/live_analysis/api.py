from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import LiveAnalysisRecord, LiveAnalysisRequest, LiveAnalysisStatus
from .service import LiveAnalysisError, live_analysis_service

router = APIRouter(prefix="/v1/live-analysis", tags=["live-analysis"])


@router.get("/status", response_model=LiveAnalysisStatus)
def status() -> LiveAnalysisStatus:
    return live_analysis_service.status()


@router.post("/evaluate", response_model=LiveAnalysisRecord)
def evaluate(payload: LiveAnalysisRequest) -> LiveAnalysisRecord:
    return live_analysis_service.evaluate(payload)


@router.get("/analyses", response_model=list[LiveAnalysisRecord])
def list_analyses() -> list[LiveAnalysisRecord]:
    return live_analysis_service.list_all()


@router.get("/analyses/{analysis_id}", response_model=LiveAnalysisRecord)
def get_analysis(analysis_id: UUID) -> LiveAnalysisRecord:
    try:
        return live_analysis_service.get(analysis_id)
    except LiveAnalysisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
