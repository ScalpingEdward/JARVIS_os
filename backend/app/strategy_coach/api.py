from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import PlaybookCreate, StrategyCoachStatus, StrategyPlaybook
from .service import strategy_coach_service


router = APIRouter(prefix="/v1/strategy-coach", tags=["strategy-coach"])


@router.get("/status", response_model=StrategyCoachStatus)
def coach_status() -> StrategyCoachStatus:
    return strategy_coach_service.status()


@router.post("/playbooks", response_model=StrategyPlaybook, status_code=status.HTTP_201_CREATED)
def create_playbook(payload: PlaybookCreate) -> StrategyPlaybook:
    return strategy_coach_service.create(payload)


@router.get("/playbooks", response_model=list[StrategyPlaybook])
def list_playbooks() -> list[StrategyPlaybook]:
    return strategy_coach_service.list_all()


@router.get("/playbooks/{playbook_id}", response_model=StrategyPlaybook)
def get_playbook(playbook_id: UUID) -> StrategyPlaybook:
    playbook = strategy_coach_service.get(playbook_id)
    if playbook is None:
        raise HTTPException(status_code=404, detail="Strategy playbook not found")
    return playbook
