from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from .models import MarketCreate, MarketRecord, RadarStatus, ResearchEvent, ResearchEventCreate
from .service import radar_service

router = APIRouter(prefix="/v1", tags=["market-radar"])


@router.get("/radar/status", response_model=RadarStatus)
def radar_status() -> RadarStatus:
    return radar_service.status()


@router.get("/radar/markets", response_model=list[MarketRecord])
def list_markets(active_only: bool = False) -> list[MarketRecord]:
    return radar_service.list_markets(active_only=active_only)


@router.post("/radar/watchlists", response_model=MarketRecord, status_code=status.HTTP_201_CREATED)
def add_watch(payload: MarketCreate) -> MarketRecord:
    return radar_service.add_market(payload)


@router.delete("/radar/watchlists/{market_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_watch(market_id: UUID) -> Response:
    if not radar_service.remove_market(market_id):
        raise HTTPException(status_code=409, detail="Core market cannot be removed or market was not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/research/events", response_model=ResearchEvent, status_code=status.HTTP_201_CREATED)
def add_research_event(payload: ResearchEventCreate) -> ResearchEvent:
    return radar_service.add_event(payload)


@router.get("/research/events", response_model=list[ResearchEvent])
def list_research_events(minimum_relevance: int = 0) -> list[ResearchEvent]:
    return radar_service.list_events(minimum_relevance=minimum_relevance)


@router.get("/research/history", response_model=list[ResearchEvent])
def research_history() -> list[ResearchEvent]:
    return radar_service.list_events()


@router.get("/radar/obsidian-export", response_class=Response)
def obsidian_export() -> Response:
    return Response(content=radar_service.export_obsidian(), media_type="text/markdown")
