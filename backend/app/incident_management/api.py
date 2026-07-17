from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ActionState, FollowUpCreate, FollowUpRecord, IncidentCreate, IncidentMetrics,
    IncidentMutation, IncidentRecord, IncidentState, IncidentStatus,
    PostmortemCreate, PostmortemRecord, PostmortemState, ResponderMutation,
    TimelineCreate, TimelineRecord,
)
from .service import incident_management_service as service

router = APIRouter(prefix="/v1/incidents", tags=["incident-management"])


@router.get("/status", response_model=IncidentStatus)
def get_status() -> IncidentStatus:
    return service.status()


@router.post("", response_model=IncidentRecord, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate) -> IncidentRecord:
    try:
        return service.create_incident(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[IncidentRecord])
def list_incidents(workspace_id: str = Query(min_length=1, max_length=120), state: IncidentState | None = None) -> list[IncidentRecord]:
    return service.list_incidents(workspace_id, state)


@router.get("/{incident_id}", response_model=IncidentRecord)
def get_incident(incident_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    item = service.get_incident(incident_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return item


def _set_incident(incident_id: UUID, workspace_id: str, payload: IncidentMutation, state: IncidentState) -> IncidentRecord:
    try:
        item = service.set_state(incident_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned incident not found")
    return item


@router.post("/{incident_id}/investigate", response_model=IncidentRecord)
def investigate(incident_id: UUID, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _set_incident(incident_id, workspace_id, payload, IncidentState.INVESTIGATING)


@router.post("/{incident_id}/mitigate", response_model=IncidentRecord)
def mitigate(incident_id: UUID, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _set_incident(incident_id, workspace_id, payload, IncidentState.MITIGATING)


@router.post("/{incident_id}/monitor", response_model=IncidentRecord)
def monitor(incident_id: UUID, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _set_incident(incident_id, workspace_id, payload, IncidentState.MONITORING)


@router.post("/{incident_id}/resolve", response_model=IncidentRecord)
def resolve(incident_id: UUID, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _set_incident(incident_id, workspace_id, payload, IncidentState.RESOLVED)


@router.post("/{incident_id}/close", response_model=IncidentRecord)
def close(incident_id: UUID, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _set_incident(incident_id, workspace_id, payload, IncidentState.CLOSED)


@router.post("/{incident_id}/cancel", response_model=IncidentRecord)
def cancel(incident_id: UUID, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    return _set_incident(incident_id, workspace_id, payload, IncidentState.CANCELLED)


@router.post("/{incident_id}/responders", response_model=IncidentRecord)
def add_responder(incident_id: UUID, payload: ResponderMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentRecord:
    item = service.add_responder(incident_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Commander-owned incident not found")
    return item


@router.post("/timeline", response_model=TimelineRecord, status_code=status.HTTP_201_CREATED)
def add_timeline(payload: TimelineCreate) -> TimelineRecord:
    try:
        return service.add_timeline(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{incident_id}/timeline", response_model=list[TimelineRecord])
def list_timeline(incident_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> list[TimelineRecord]:
    return service.list_timeline(workspace_id, incident_id)


@router.post("/follow-ups", response_model=FollowUpRecord, status_code=status.HTTP_201_CREATED)
def create_follow_up(payload: FollowUpCreate) -> FollowUpRecord:
    try:
        return service.create_follow_up(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/follow-ups/list", response_model=list[FollowUpRecord])
def list_follow_ups(workspace_id: str = Query(min_length=1, max_length=120), incident_id: UUID | None = None) -> list[FollowUpRecord]:
    return service.list_follow_ups(workspace_id, incident_id)


@router.post("/follow-ups/{action_id}/{state}", response_model=FollowUpRecord)
def set_follow_up_state(action_id: UUID, state: ActionState, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FollowUpRecord:
    try:
        item = service.set_follow_up_state(action_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Assigned follow-up action not found")
    return item


@router.post("/postmortems", response_model=PostmortemRecord, status_code=status.HTTP_201_CREATED)
def create_postmortem(payload: PostmortemCreate) -> PostmortemRecord:
    try:
        return service.create_postmortem(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/postmortems/list", response_model=list[PostmortemRecord])
def list_postmortems(workspace_id: str = Query(min_length=1, max_length=120), incident_id: UUID | None = None) -> list[PostmortemRecord]:
    return service.list_postmortems(workspace_id, incident_id)


@router.post("/postmortems/{postmortem_id}/{state}", response_model=PostmortemRecord)
def set_postmortem_state(postmortem_id: UUID, state: PostmortemState, payload: IncidentMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PostmortemRecord:
    try:
        item = service.set_postmortem_state(postmortem_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned postmortem not found")
    return item


@router.get("/metrics/summary", response_model=IncidentMetrics)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> IncidentMetrics:
    return service.metrics(workspace_id)


@router.get("/audit/list")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
