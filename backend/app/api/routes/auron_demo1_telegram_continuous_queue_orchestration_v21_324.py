from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import (
    _active_sequence_store,
    _circuit_store,
    _supervision_store,
)
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store

router = APIRouter(prefix='/auron/demo1/v21.324', tags=['auron-demo1-telegram-continuous-queue-orchestration'])

_queue_store: dict[str, list[dict]] = {}
_queue_item_store: dict[str, dict] = {}
_MAX_QUEUE_DEPTH = 25


class TelegramContinuousQueueEnqueueRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=100, ge=1, le=1000)


class TelegramContinuousQueueDispatchRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)


class TelegramContinuousQueueCompleteRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    queue_item_id: str = Field(min_length=1, max_length=160)
    success: bool
    failure_reason: str | None = Field(default=None, max_length=500)


def reset_telegram_continuous_queue_orchestration_store() -> None:
    _queue_store.clear()
    _queue_item_store.clear()


def _active_go_live(chat_id: str) -> dict:
    item = _go_live_store.get(chat_id)
    if item is None or not item.get('continuous_mode_active'):
        raise HTTPException(status_code=409, detail='Active Telegram continuous-mode go-live acceptance required')
    return item


def _circuit_closed(chat_id: str) -> bool:
    return _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed'


@router.post('/enqueue')
def enqueue_continuous_conversation(payload: TelegramContinuousQueueEnqueueRequest) -> dict:
    existing = _queue_item_store.get(payload.update_id)
    if existing is not None:
        return {'state': 'telegram-continuous-conversation-already-queued', 'queue_item': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    go_live = _active_go_live(payload.telegram_chat_id)
    if not _circuit_closed(payload.telegram_chat_id):
        raise HTTPException(status_code=409, detail='Telegram safety circuit is open for this chat')
    supervision = _supervision_store.get(payload.update_id)
    if supervision is None or supervision.get('supervision_state') != 'admitted-sequenced-in-progress':
        raise HTTPException(status_code=409, detail='Admitted v21.323 supervision required before queueing')

    queue = _queue_store.setdefault(payload.telegram_chat_id, [])
    if len(queue) >= _MAX_QUEUE_DEPTH:
        raise HTTPException(status_code=429, detail={'message': 'Telegram continuous queue backpressure active', 'queue_depth': len(queue), 'max_queue_depth': _MAX_QUEUE_DEPTH})

    record = {
        'queue_item_id': str(uuid4()),
        'update_id': payload.update_id,
        'telegram_chat_id': payload.telegram_chat_id,
        'supervision_id': supervision['supervision_id'],
        'go_live_acceptance_id': go_live['go_live_acceptance_id'],
        'priority': payload.priority,
        'queue_state': 'queued-awaiting-supervised-dispatch',
        'enqueued_by': payload.actor,
        'enqueued_at': datetime.now(timezone.utc).isoformat(),
        'dispatched_at': None,
        'completed_at': None,
        'external_calls_made': 0,
    }
    queue.append(record)
    queue.sort(key=lambda item: (item['priority'], item['enqueued_at']))
    _queue_item_store[payload.update_id] = record
    return {'state': 'telegram-continuous-conversation-queued', 'queue_item': record, 'queue_depth': len(queue), 'external_calls_made': 0}


@router.post('/dispatch-next')
def dispatch_next_continuous_conversation(payload: TelegramContinuousQueueDispatchRequest) -> dict:
    _active_go_live(payload.telegram_chat_id)
    if not _circuit_closed(payload.telegram_chat_id):
        raise HTTPException(status_code=409, detail='Telegram safety circuit is open for this chat')
    if payload.telegram_chat_id in _active_sequence_store:
        raise HTTPException(status_code=409, detail='Per-chat sequence is busy; supervised dispatch deferred')

    queue = _queue_store.get(payload.telegram_chat_id, [])
    pending = next((item for item in queue if item.get('queue_state') == 'queued-awaiting-supervised-dispatch'), None)
    if pending is None:
        raise HTTPException(status_code=404, detail='No queued Telegram conversation available')

    pending['queue_state'] = 'dispatched-awaiting-lifecycle-progression'
    pending['dispatched_by'] = payload.actor
    pending['dispatched_at'] = datetime.now(timezone.utc).isoformat()
    return {
        'state': 'telegram-continuous-conversation-dispatched',
        'queue_item': pending,
        'automatic_progression_plan': ['conversation-dispatch', 'delivery-admission', 'execution-preparation', 'runtime-worker', 'result-correlation', 'lifecycle-closure'],
        'external_calls_made': 0,
        'next_layer': 'supervised-automatic-lifecycle-progression',
    }


@router.post('/complete')
def complete_queue_item(payload: TelegramContinuousQueueCompleteRequest) -> dict:
    item = next((record for record in _queue_item_store.values() if record.get('queue_item_id') == payload.queue_item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail='Telegram continuous queue item not found')
    if item.get('queue_state') in {'completed', 'failed'}:
        return {'state': 'telegram-continuous-queue-item-already-terminal', 'queue_item': item, 'idempotent_replay': True, 'external_calls_made': 0}
    if item.get('queue_state') != 'dispatched-awaiting-lifecycle-progression':
        raise HTTPException(status_code=409, detail='Telegram queue item has not been dispatched')

    item['queue_state'] = 'completed' if payload.success else 'failed'
    item['failure_reason'] = None if payload.success else payload.failure_reason or 'unspecified-failure'
    item['completed_by'] = payload.actor
    item['completed_at'] = datetime.now(timezone.utc).isoformat()
    return {'state': 'telegram-continuous-queue-item-completed', 'queue_item': item, 'external_calls_made': 0}


@router.get('/status')
def queue_status() -> dict:
    items = list(_queue_item_store.values())
    return {
        'queue_items': len(items),
        'queued': sum(1 for item in items if item['queue_state'] == 'queued-awaiting-supervised-dispatch'),
        'dispatched': sum(1 for item in items if item['queue_state'] == 'dispatched-awaiting-lifecycle-progression'),
        'completed': sum(1 for item in items if item['queue_state'] == 'completed'),
        'failed': sum(1 for item in items if item['queue_state'] == 'failed'),
        'max_queue_depth_per_chat': _MAX_QUEUE_DEPTH,
        'external_calls_made': 0,
        'orchestration_mode': 'per-chat-priority-queue-backpressure-supervised-progression',
    }


@router.get('/items')
def list_queue_items() -> dict:
    items = sorted(_queue_item_store.values(), key=lambda item: item['enqueued_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import command_center as v21_323_command_center
    html = v21_323_command_center().replace('v21.323', 'v21.324')
    return html.replace('AURON TELEGRAM CONTINUOUS CONVERSATION SUPERVISOR COMMAND CENTER', 'AURON TELEGRAM CONTINUOUS QUEUE ORCHESTRATION COMMAND CENTER')
