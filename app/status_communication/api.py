from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalCreate, ApprovalRecord, CommunicationCreate, CommunicationRecord,
    ComponentRecord, ComponentStatusUpdate, MessageState, MetricsRecord, Mutation,
    PageState, StatusCommunicationStatus, StatusPageCreate, StatusPageRecord,
)
from .service import status_communication_service as service

router = APIRouter(prefix="/v1/status-communication", tags=["status-communication"])


@router.get("/status", response_model=StatusCommunicationStatus)
def get_status() -> StatusCommunicationStatus:
    return service.status()


@router.post("/pages", response_model=StatusPageRecord, status_code=status.HTTP_201_CREATED)
def create_page(payload: StatusPageCreate) -> StatusPageRecord:
    try:
        return service.create_page(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/pages", response_model=list[StatusPageRecord])
def list_pages(workspace_id: str = Query(min_length=1, max_length=120), state: PageState | None = None) -> list[StatusPageRecord]:
    return service.list_pages(workspace_id, state)


@router.get("/pages/{page_id}", response_model=StatusPageRecord)
def get_page(page_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> StatusPageRecord:
    item = service.get_page(page_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Status page not found")
    return item


def _set_page(page_id: UUID, workspace_id: str, payload: Mutation, state: PageState) -> StatusPageRecord:
    try:
        item = service.set_page_state(page_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned status page not found")
    return item


@router.post("/pages/{page_id}/activate", response_model=StatusPageRecord)
def activate_page(page_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> StatusPageRecord:
    return _set_page(page_id, workspace_id, payload, PageState.ACTIVE)


@router.post("/pages/{page_id}/pause", response_model=StatusPageRecord)
def pause_page(page_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> StatusPageRecord:
    return _set_page(page_id, workspace_id, payload, PageState.PAUSED)


@router.post("/pages/{page_id}/retire", response_model=StatusPageRecord)
def retire_page(page_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> StatusPageRecord:
    return _set_page(page_id, workspace_id, payload, PageState.RETIRED)


@router.post("/components/status", response_model=ComponentRecord)
def update_component_status(payload: ComponentStatusUpdate) -> ComponentRecord:
    try:
        return service.update_component(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/communications", response_model=CommunicationRecord, status_code=status.HTTP_201_CREATED)
def create_communication(payload: CommunicationCreate) -> CommunicationRecord:
    try:
        return service.create_message(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/communications", response_model=list[CommunicationRecord])
def list_communications(workspace_id: str = Query(min_length=1, max_length=120), state: MessageState | None = None, page_id: UUID | None = None) -> list[CommunicationRecord]:
    return service.list_messages(workspace_id, state, page_id)


def _set_message(message_id: UUID, workspace_id: str, payload: Mutation, state: MessageState) -> CommunicationRecord:
    try:
        item = service.set_message_state(message_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned communication not found")
    return item


@router.post("/communications/{message_id}/review", response_model=CommunicationRecord)
def submit_review(message_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> CommunicationRecord:
    return _set_message(message_id, workspace_id, payload, MessageState.REVIEW)


@router.post("/approvals", response_model=ApprovalRecord, status_code=status.HTTP_201_CREATED)
def approve(payload: ApprovalCreate) -> ApprovalRecord:
    try:
        return service.approve(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/communications/{message_id}/publish", response_model=CommunicationRecord)
def publish(message_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> CommunicationRecord:
    return _set_message(message_id, workspace_id, payload, MessageState.PUBLISHED)


@router.post("/communications/{message_id}/archive", response_model=CommunicationRecord)
def archive(message_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> CommunicationRecord:
    return _set_message(message_id, workspace_id, payload, MessageState.ARCHIVED)


@router.post("/communications/{message_id}/cancel", response_model=CommunicationRecord)
def cancel(message_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> CommunicationRecord:
    return _set_message(message_id, workspace_id, payload, MessageState.CANCELLED)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
