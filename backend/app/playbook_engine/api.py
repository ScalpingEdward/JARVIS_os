from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ActorAction,
    DryRunCreate,
    DryRunRecord,
    PlaybookCreate,
    PlaybookEngineStatus,
    PlaybookMetrics,
    PlaybookRecord,
)
from .service import playbook_engine_service

router = APIRouter(prefix="/v1/playbook-engine", tags=["playbook-engine"])


def _translate(error: Exception) -> None:
    if isinstance(error, KeyError):
        raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
    raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/status", response_model=PlaybookEngineStatus)
def engine_status() -> PlaybookEngineStatus:
    return playbook_engine_service.status()


@router.post("/playbooks", response_model=PlaybookRecord, status_code=status.HTTP_201_CREATED)
def create_playbook(payload: PlaybookCreate) -> PlaybookRecord:
    try:
        return playbook_engine_service.create(payload)
    except (ValueError, KeyError) as error:
        _translate(error)


@router.get("/playbooks", response_model=list[PlaybookRecord])
def list_playbooks(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PlaybookRecord]:
    return playbook_engine_service.list_all(workspace_id)


@router.get("/playbooks/{playbook_id}", response_model=PlaybookRecord)
def get_playbook(playbook_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> PlaybookRecord:
    item = playbook_engine_service.get(playbook_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="playbook not found")
    return item


@router.post("/playbooks/{playbook_id}/review", response_model=PlaybookRecord)
def review_playbook(playbook_id: UUID, payload: ActorAction, workspace_id: str = Query(min_length=1, max_length=120)) -> PlaybookRecord:
    try:
        return playbook_engine_service.submit_review(playbook_id, workspace_id, payload)
    except (ValueError, KeyError) as error:
        _translate(error)


@router.post("/playbooks/{playbook_id}/approve", response_model=PlaybookRecord)
def approve_playbook(playbook_id: UUID, payload: ActorAction, workspace_id: str = Query(min_length=1, max_length=120)) -> PlaybookRecord:
    try:
        return playbook_engine_service.approve(playbook_id, workspace_id, payload)
    except (ValueError, KeyError) as error:
        _translate(error)


@router.post("/playbooks/{playbook_id}/publish", response_model=PlaybookRecord)
def publish_playbook(playbook_id: UUID, payload: ActorAction, workspace_id: str = Query(min_length=1, max_length=120)) -> PlaybookRecord:
    try:
        return playbook_engine_service.publish(playbook_id, workspace_id, payload)
    except (ValueError, KeyError) as error:
        _translate(error)


@router.post("/playbooks/{playbook_id}/retire", response_model=PlaybookRecord)
def retire_playbook(playbook_id: UUID, payload: ActorAction, workspace_id: str = Query(min_length=1, max_length=120)) -> PlaybookRecord:
    try:
        return playbook_engine_service.retire(playbook_id, workspace_id, payload)
    except (ValueError, KeyError) as error:
        _translate(error)


@router.post("/playbooks/{playbook_id}/dry-runs", response_model=DryRunRecord, status_code=status.HTTP_201_CREATED)
def create_dry_run(playbook_id: UUID, payload: DryRunCreate) -> DryRunRecord:
    try:
        return playbook_engine_service.dry_run(playbook_id, payload)
    except (ValueError, KeyError) as error:
        _translate(error)


@router.get("/dry-runs", response_model=list[DryRunRecord])
def list_dry_runs(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DryRunRecord]:
    return playbook_engine_service.list_dry_runs(workspace_id)


@router.get("/metrics", response_model=PlaybookMetrics)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> PlaybookMetrics:
    return playbook_engine_service.metrics(workspace_id)


@router.get("/audit", response_model=list[dict])
def audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[dict]:
    return playbook_engine_service.list_audit(workspace_id)
