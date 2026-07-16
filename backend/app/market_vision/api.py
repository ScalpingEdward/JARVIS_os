from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..autonomous_research.api import router as autonomous_research_router
from .models import MarketVisionCreate, MarketVisionListResponse, MarketVisionRecord, MarketVisionStatus
from .service import market_vision_service


router = APIRouter(prefix="/v1/market-vision", tags=["market-vision"])


@router.get("/status", response_model=MarketVisionStatus)
def vision_status() -> MarketVisionStatus:
    return market_vision_service.status()


@router.post("/analyses", response_model=MarketVisionRecord, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: MarketVisionCreate) -> MarketVisionRecord:
    return market_vision_service.create(payload)


@router.get("/analyses", response_model=MarketVisionListResponse)
def list_analyses(symbol: str | None = Query(default=None, max_length=40)) -> MarketVisionListResponse:
    items = market_vision_service.list_all(symbol=symbol)
    return MarketVisionListResponse(items=items, count=len(items))


@router.get("/analyses/{analysis_id}", response_model=MarketVisionRecord)
def get_analysis(analysis_id: UUID) -> MarketVisionRecord:
    record = market_vision_service.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market vision analysis not found")
    return record


@router.get("/latest/{symbol}", response_model=MarketVisionRecord)
def latest_analysis(symbol: str) -> MarketVisionRecord:
    record = market_vision_service.latest(symbol)
    if record is None:
        raise HTTPException(status_code=404, detail="No market vision analysis found")
    return record


# Register the independent research-network API through an already mounted router.
router.include_router(autonomous_research_router)
