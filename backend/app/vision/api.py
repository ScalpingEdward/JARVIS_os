from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import LiveFeedCreate, LiveFeedRecord, LiveFrameIngest, VisionAnalysis, VisionFrameCreate, VisionStatus
from .service import VisionError, vision_service

router = APIRouter(prefix="/v1/vision", tags=["vision"])


@router.get("/status", response_model=VisionStatus)
def status() -> VisionStatus:
    return vision_service.status()


@router.post("/analyze", response_model=VisionAnalysis)
def analyze(payload: VisionFrameCreate) -> VisionAnalysis:
    return vision_service.analyze(payload)


@router.get("/analyses/{analysis_id}", response_model=VisionAnalysis)
def get_analysis(analysis_id: UUID) -> VisionAnalysis:
    try:
        return vision_service.get(analysis_id)
    except VisionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/feeds", response_model=LiveFeedRecord)
def create_feed(payload: LiveFeedCreate) -> LiveFeedRecord:
    try:
        return vision_service.create_feed(payload)
    except VisionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/feeds", response_model=list[LiveFeedRecord])
def list_feeds() -> list[LiveFeedRecord]:
    return vision_service.list_feeds()


@router.post("/feeds/{feed_id}/frames", response_model=VisionAnalysis)
def ingest_frame(feed_id: UUID, payload: LiveFrameIngest) -> VisionAnalysis:
    try:
        return vision_service.ingest_live_frame(feed_id, payload)
    except VisionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
