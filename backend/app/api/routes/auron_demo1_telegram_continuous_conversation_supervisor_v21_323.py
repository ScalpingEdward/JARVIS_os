from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store

router = APIRouter(prefix='/auron/demo1/v21.323', tags=['auron-demo1-telegram-continuous-conversation-supervisor'])

_supervision_store: dict[str, dict] = {}
_chat_event_store: dict[str, list[dict]] = {}
_active_sequence_store: dict[str, dict] = {}
_circuit_store: dict[str, dict] = {}


class TelegramConversationAdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    sequence_key: str = Field(min_length=1, max_length=160)
    observed_at: datetime | None = None


class TelegramConversationCompletionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    success: bool
    failure_reason: str | None = Field(default=None, max_length=500)


class TelegramCircuitResetRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    reset_phrase: str = Field(min_length=1, max_length=200)


_RESET_PHRASE = 'RESET AURON TELEGRAM SAFETY CIRCUIT'
_MAX_CONSECUTIVE_FAILURES = 3


def reset_telegram_continuous_conversation_supervisor_store() -> None:
    _supervision_store.clear()
    _chat_event_store.clear()
    _active_sequence_store.clear()
    _circuit_store.clear()


def _go_live(chat_id: str) -> dict:
    record = _go_live_store.get(chat_id)
    if record is None or not record.get('continuous_mode_active'):
        raise HTTPException(status_code=409, detail='Active Telegram continuous-mode go-live acceptance required')
    return record


def _circuit(chat_id: str) -> dict:
    return _circuit_store.setdefault(chat_id, {
        'telegram_chat_id': chat_id,
        'state': 'closed',
        'consecutive_failures': 0,
        'opened_at': None,
        'opened_reason': None,
        'reset_at': None,
        'reset_by': None,
    })


def _recent_events(chat_id: str, observed_at: datetime) -> list[dict]:
    cutoff = observed_at - timedelta(minutes=1)
    return [item for item in _chat_event_store.get(chat_id, []) if datetime.fromisoformat(item['observed_at']) >= cutoff]


@router.post('/admit')
def admit_continuous_conversation(payload: TelegramConversationAdmissionRequest) -> dict:
    existing = _supervision_store.get(payload.update_id)
    if existing is not None:
        return {'state': 'telegram-continuous-conversation-already-supervised', 'supervision': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    go_live = _go_live(payload.telegram_chat_id)
    circuit = _circuit(payload.telegram_chat_id)
    if circuit['state'] == 'open':
        raise HTTPException(status_code=409, detail='Telegram safety circuit is open for this chat')

    observed_at = payload.observed_at or datetime.now(timezone.utc)
    recent = _recent_events(payload.telegram_chat_id, observed_at)
    rate_limit = int(go_live['max_messages_per_minute'])
    active = _active_sequence_store.get(payload.telegram_chat_id)
    checks = {
        'continuous_mode_active': True,
        'circuit_closed': circuit['state'] == 'closed',
        'rate_limit_available': len(recent) < rate_limit,
        'chat_sequence_available': active is None,
        'concurrency_available': 0 if active is None else 1 < int(go_live['max_concurrent_conversations']),
    }
    if active is None:
        checks['concurrency_available'] = True
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        if 'rate_limit_available' in blockers:
            circuit.update(state='open', opened_at=datetime.now(timezone.utc).isoformat(), opened_reason='rate-limit-exceeded')
            go_live['continuous_mode_active'] = False
            go_live['go_live_state'] = 'paused-by-safety-circuit'
        raise HTTPException(status_code=429 if 'rate_limit_available' in blockers else 409, detail={'message': 'Telegram continuous conversation admission blocked', 'blockers': blockers})

    event = {
        'event_id': str(uuid4()),
        'update_id': payload.update_id,
        'sequence_key': payload.sequence_key,
        'observed_at': observed_at.isoformat(),
    }
    _chat_event_store.setdefault(payload.telegram_chat_id, []).append(event)
    _active_sequence_store[payload.telegram_chat_id] = event
    record = {
        'supervision_id': str(uuid4()),
        'update_id': payload.update_id,
        'telegram_chat_id': payload.telegram_chat_id,
        'sequence_key': payload.sequence_key,
        'go_live_acceptance_id': go_live['go_live_acceptance_id'],
        'supervision_state': 'admitted-sequenced-in-progress',
        'checks': checks,
        'admitted_by': payload.actor,
        'admitted_at': datetime.now(timezone.utc).isoformat(),
        'completed_at': None,
        'external_calls_made': 0,
    }
    _supervision_store[payload.update_id] = record
    return {'state': 'telegram-continuous-conversation-admitted', 'supervision': record, 'external_calls_made': 0, 'next_layer': 'telegram-continuous-conversation-runtime-dispatch'}


@router.post('/complete')
def complete_continuous_conversation(payload: TelegramConversationCompletionRequest) -> dict:
    record = _supervision_store.get(payload.update_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram supervised conversation not found')
    if record.get('supervision_state') in {'completed', 'failed'}:
        return {'state': 'telegram-continuous-conversation-already-completed', 'supervision': record, 'idempotent_replay': True, 'external_calls_made': 0}
    if record.get('telegram_chat_id') != payload.telegram_chat_id:
        raise HTTPException(status_code=409, detail='Telegram chat does not match supervised conversation')

    circuit = _circuit(payload.telegram_chat_id)
    record['completed_at'] = datetime.now(timezone.utc).isoformat()
    record['completed_by'] = payload.actor
    if payload.success:
        record['supervision_state'] = 'completed'
        circuit['consecutive_failures'] = 0
    else:
        record['supervision_state'] = 'failed'
        record['failure_reason'] = payload.failure_reason or 'unspecified-failure'
        circuit['consecutive_failures'] += 1
        if circuit['consecutive_failures'] >= _MAX_CONSECUTIVE_FAILURES:
            circuit.update(state='open', opened_at=record['completed_at'], opened_reason='consecutive-failure-threshold')
            go_live = _go_live_store.get(payload.telegram_chat_id)
            if go_live:
                go_live['continuous_mode_active'] = False
                go_live['go_live_state'] = 'paused-by-safety-circuit'
    _active_sequence_store.pop(payload.telegram_chat_id, None)
    return {'state': 'telegram-continuous-conversation-completed', 'supervision': record, 'circuit': circuit, 'external_calls_made': 0}


@router.post('/circuit/reset')
def reset_safety_circuit(payload: TelegramCircuitResetRequest) -> dict:
    if payload.reset_phrase != _RESET_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram safety-circuit reset approval required')
    circuit = _circuit(payload.telegram_chat_id)
    if circuit['state'] == 'closed':
        return {'state': 'telegram-safety-circuit-already-closed', 'circuit': circuit, 'idempotent_replay': True, 'external_calls_made': 0}
    circuit.update(state='closed', consecutive_failures=0, reset_at=datetime.now(timezone.utc).isoformat(), reset_by=payload.actor)
    return {'state': 'telegram-safety-circuit-reset', 'circuit': circuit, 'external_calls_made': 0}


@router.get('/status')
def supervisor_status() -> dict:
    return {
        'supervised_conversations': len(_supervision_store),
        'active_sequences': len(_active_sequence_store),
        'open_circuits': sum(1 for item in _circuit_store.values() if item['state'] == 'open'),
        'completed': sum(1 for item in _supervision_store.values() if item['supervision_state'] == 'completed'),
        'failed': sum(1 for item in _supervision_store.values() if item['supervision_state'] == 'failed'),
        'external_calls_made': 0,
        'supervisor_mode': 'per-chat-sequenced-rate-limited-circuit-protected',
    }


@router.get('/supervisions')
def list_supervisions() -> dict:
    items = sorted(_supervision_store.values(), key=lambda item: item['admitted_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/circuits')
def list_circuits() -> dict:
    return {'count': len(_circuit_store), 'items': list(_circuit_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import command_center as v21_322_command_center
    html = v21_322_command_center().replace('v21.322', 'v21.323')
    return html.replace('AURON TELEGRAM OPERATIONAL GO LIVE ACCEPTANCE COMMAND CENTER', 'AURON TELEGRAM CONTINUOUS CONVERSATION SUPERVISOR COMMAND CENTER')
