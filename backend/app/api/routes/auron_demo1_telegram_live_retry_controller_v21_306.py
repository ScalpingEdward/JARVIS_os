from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_live_transport_adapter_v21_304 import _live_execution_store
from app.api.routes.auron_demo1_telegram_live_delivery_state_commit_v21_305 import _live_delivery_commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.306', tags=['auron-demo1-telegram-live-retry-controller'])

_live_retry_store: dict[str, dict] = {}


class TelegramLiveRetryScheduleRequest(BaseModel):
    live_delivery_commit_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_backoff_seconds: int = Field(default=30, ge=1, le=3600)


def reset_telegram_live_retry_controller_store() -> None:
    _live_retry_store.clear()


def _commit_by_id(commit_id: str) -> dict | None:
    return next((item for item in _live_delivery_commit_store.values() if item['live_delivery_commit_id'] == commit_id), None)


def _execution_by_id(execution_id: str) -> dict | None:
    return next((item for item in _live_execution_store.values() if item['execution_id'] == execution_id), None)


@router.get('/status')
def telegram_live_retry_status() -> dict:
    return {
        'live_retries': len(_live_retry_store),
        'scheduled': sum(1 for item in _live_retry_store.values() if item['retry_state'] == 'scheduled'),
        'exhausted': sum(1 for item in _live_retry_store.values() if item['retry_state'] == 'retry-exhausted'),
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'controller_mode': 'controlled-live-retry-scheduling',
    }


@router.post('/schedule')
def schedule_live_retry(payload: TelegramLiveRetryScheduleRequest) -> dict:
    existing = _live_retry_store.get(payload.live_delivery_commit_id)
    if existing is not None:
        return {
            'state': 'telegram-live-retry-already-scheduled',
            'retry': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    commit = _commit_by_id(payload.live_delivery_commit_id)
    if commit is None:
        raise HTTPException(status_code=404, detail='Telegram live delivery commit not found')
    if commit.get('delivery_state') != 'retry-required' or commit.get('terminal') is True:
        raise HTTPException(status_code=409, detail='Retry-required non-terminal Telegram live delivery commit required')

    execution = _execution_by_id(commit['execution_id'])
    outbound = _outbound_store.get(commit['correlation_id'])
    if execution is None or outbound is None:
        raise HTTPException(status_code=409, detail='Correlated Telegram live execution and outbound required')
    if execution.get('live_delivery_commit_id') != commit['live_delivery_commit_id']:
        raise HTTPException(status_code=409, detail='Telegram live retry execution correlation mismatch')

    previous_attempt = int(execution.get('attempt', 1))
    next_attempt = previous_attempt + 1
    now = datetime.now(timezone.utc)
    if next_attempt > payload.max_attempts:
        retry_state = 'retry-exhausted'
        eligible_at = None
        terminal = True
        commit['delivery_state'] = 'retry-exhausted'
        commit['terminal'] = True
        outbound['delivery_state'] = 'retry-exhausted'
        next_layer = 'telegram-live-terminal-audit'
    else:
        delay = payload.base_backoff_seconds * (2 ** max(0, next_attempt - 2))
        retry_state = 'scheduled'
        eligible_at = (now + timedelta(seconds=delay)).isoformat()
        terminal = False
        commit['delivery_state'] = 'retry-scheduled'
        outbound['delivery_state'] = 'retry-scheduled'
        next_layer = 'telegram-live-controlled-retry-dispatch'

    record = {
        'live_retry_id': str(uuid4()),
        'live_delivery_commit_id': commit['live_delivery_commit_id'],
        'execution_id': commit['execution_id'],
        'correlation_id': commit['correlation_id'],
        'activation_id': commit['activation_id'],
        'provider_id': commit['provider_id'],
        'runtime_id': commit['runtime_id'],
        'outbound_id': commit['outbound_id'],
        'dispatch_id': commit['dispatch_id'],
        'attempt': next_attempt,
        'max_attempts': payload.max_attempts,
        'base_backoff_seconds': payload.base_backoff_seconds,
        'eligible_at': eligible_at,
        'retry_state': retry_state,
        'terminal': terminal,
        'scheduled_by': payload.actor,
        'scheduled_at': now.isoformat(),
    }
    _live_retry_store[payload.live_delivery_commit_id] = record
    execution['attempt'] = next_attempt
    execution['max_attempts'] = payload.max_attempts
    execution['execution_state'] = 'retry-exhausted' if terminal else 'retry-scheduled'
    execution['live_retry_id'] = record['live_retry_id']
    commit['live_retry_id'] = record['live_retry_id']
    commit['retry_state'] = retry_state
    outbound['live_retry_id'] = record['live_retry_id']

    return {
        'state': 'telegram-live-retry-exhausted' if terminal else 'telegram-live-retry-scheduled',
        'retry': record,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': next_layer,
    }


@router.get('/retries')
def list_live_retries() -> dict:
    items = sorted(_live_retry_store.values(), key=lambda item: item['scheduled_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_live_delivery_state_commit_v21_305 import command_center as v21_305_command_center

    html = v21_305_command_center()
    html = html.replace('v21.305', 'v21.306')
    html = html.replace(
        'AURON TELEGRAM LIVE DELIVERY STATE COMMIT COMMAND CENTER',
        'AURON TELEGRAM LIVE RETRY CONTROLLER COMMAND CENTER',
    )
    return html
