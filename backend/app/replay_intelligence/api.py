from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import JournalEntry, JournalEntryCreate, JournalSummary, ReplayIntelligenceStatus
from .service import replay_intelligence_service


router = APIRouter(prefix="/v1/replay-intelligence", tags=["replay-intelligence"])


@router.get("/status", response_model=ReplayIntelligenceStatus)
def intelligence_status() -> ReplayIntelligenceStatus:
    return replay_intelligence_service.status()


@router.post("/journal", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
def create_journal_entry(payload: JournalEntryCreate) -> JournalEntry:
    return replay_intelligence_service.create(payload)


@router.get("/journal", response_model=list[JournalEntry])
def list_journal_entries(
    replay_session_id: UUID | None = Query(default=None),
) -> list[JournalEntry]:
    return replay_intelligence_service.list_all(replay_session_id)


@router.get("/journal/{entry_id}", response_model=JournalEntry)
def get_journal_entry(entry_id: UUID) -> JournalEntry:
    entry = replay_intelligence_service.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.get("/summary", response_model=JournalSummary)
def journal_summary(
    replay_session_id: UUID | None = Query(default=None),
) -> JournalSummary:
    return replay_intelligence_service.summary(replay_session_id)
