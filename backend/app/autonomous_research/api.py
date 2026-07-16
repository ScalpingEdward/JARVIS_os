from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import EventState, ResearchBrief, ResearchEvent, ResearchEventCreate, ResearchEventList, ResearchStatus
from .service import autonomous_research_service

router = APIRouter(prefix="/v1/research-network", tags=["research-network"])


@router.get("/status", response_model=ResearchStatus)
def research_status() -> ResearchStatus:
    return autonomous_research_service.status()


@router.post("/events", response_model=ResearchEvent, status_code=status.HTTP_201_CREATED)
def create_event(payload: ResearchEventCreate) -> ResearchEvent:
    return autonomous_research_service.create(payload)


@router.get("/events", response_model=ResearchEventList)
def list_events(
    event_state: EventState | None = None,
    min_relevance: float = Query(default=0, ge=0, le=1),
) -> ResearchEventList:
    items = autonomous_research_service.list_all(state=event_state, min_relevance=min_relevance)
    return ResearchEventList(items=items, count=len(items))


@router.get("/events/{event_id}", response_model=ResearchEvent)
def get_event(event_id: UUID) -> ResearchEvent:
    event = autonomous_research_service.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Research event not found")
    return event


@router.get("/brief", response_model=ResearchBrief)
def research_brief(limit: int = Query(default=10, ge=1, le=100)) -> ResearchBrief:
    return autonomous_research_service.brief(limit=limit)
