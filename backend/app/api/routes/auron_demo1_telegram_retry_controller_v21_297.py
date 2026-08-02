from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_delivery_state_commit_v21_296 import _commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.297', tags=['auron-demo1-telegram-retry-controller'])

_retry_store: dict[str, dict] = {}


class TelegramRetryScheduleRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    backoff_seconds: int = Field(default=30, ge=1, le=3600)
    dry_run: bool = True


def reset_telegram_retry_controller_store() -> None:
    _retry_store.clear()


def _retry_key(correlation_id: str, attempt: int) -> str:
    return f'{correlation_id}:{attempt}'


@router.get('/status')
def telegram_retry_status() -> dict:
    scheduled = sum(1 for item in _retry_store.values() if item['retry_state'] == 'scheduled')
    exhausted = sum(1 for item in _retry_store.values() if item['retry_state'] == 'exhausted')
    return {
        'retry_records': len(_retry_store),
        'scheduled_retries': scheduled,
        'exhausted_retries': exhausted,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'controller_mode': 'bounded-dry-run-retry-scheduling',
    }


@router.post('/schedule')
def schedule_telegram_retry(payload: TelegramRetryScheduleRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram retry execution is not enabled in v21.297')

    commit = _commit_store.get(payload.correlation_id)
    if commit is None:
        raise HTTPException(status_code=404, detail='Telegram delivery commit not found')
    if commit.get('delivery_state') != 'retry-scheduled' or commit.get('terminal') is not False:
        raise HTTPException(status_code=409, detail='Retryable non-terminal Telegram delivery commit required')

    current_attempt = int(commit.get('attempt', 1))
    next_attempt = current_attempt + 1
    max_attempts = int(commit.get('max_attempts', 3))
    key = _retry_key(payload.correlation_id, next_attempt)
    existing = _retry_store.get(key)
    if existing is not None:
        return {
            'state': 'telegram-retry-already-scheduled',
            'retry': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    now = datetime.now(timezone.utc)
    if next_attempt > max_attempts:
        record = {
            'retry_id': str(uuid4()),
            'correlation_id': payload.correlation_id,
            'delivery_commit_id': commit['commit_id'],
            'attempt': current_attempt,
            'next_attempt': next_attempt,
            'max_attempts': max_attempts,
            'retry_state': 'exhausted',
            'eligible_at': None,
            'scheduled_by': payload.actor,
            'scheduled_at': now.isoformat(),
            'provider_call_performed': False,
            'message_sent': False,
        }
        _retry_store[key] = record
        commit['delivery_state'] = 'retry-exhausted'
        commit['terminal'] = True
        commit['retry_exhausted_at'] = now.isoformat()
        outbound = _outbound_store.get(payload.correlation_id)
        if outbound is not None:
            outbound['delivery_state'] = 'retry-exhausted'
        return {
            'state': 'telegram-retry-budget-exhausted',
            'retry': record,
            'provider_api_calls_made': 0,
            'outbound_messages_sent': 0,
            'external_calls_made': 0,
            'next_layer': 'telegram-delivery-audit',
        }

    eligible_at = now + timedelta(seconds=payload.backoff_seconds)
    record = {
        'retry_id': str(uuid4()),
        'correlation_id': payload.correlation_id,
        'delivery_commit_id': commit['commit_id'],
        'previous_attempt': current_attempt,
        'attempt': next_attempt,
        'max_attempts': max_attempts,
        'backoff_seconds': payload.backoff_seconds,
        'eligible_at': eligible_at.isoformat(),
        'retry_state': 'scheduled',
        'scheduled_by': payload.actor,
        'scheduled_at': now.isoformat(),
        'provider_call_performed': False,
        'message_sent': False,
    }
    _retry_store[key] = record
    commit['retry_id'] = record['retry_id']
    commit['next_attempt'] = next_attempt
    commit['retry_eligible_at'] = record['eligible_at']
    return {
        'state': 'telegram-retry-scheduled',
        'retry': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-controlled-retry-dispatch',
        'reply': 'Telegram-Retry wurde mit begrenztem Attempt-Budget geplant. Noch wurde kein Provider aufgerufen.',
    }


@router.get('/retries')
def list_telegram_retries() -> dict:
    items = sorted(_retry_store.values(), key=lambda item: item['scheduled_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_delivery_state_commit_v21_296 import command_center as v21_296_command_center

    html = v21_296_command_center()
    html = html.replace('v21.296', 'v21.297')
    html = html.replace(
        'AURON TELEGRAM DELIVERY STATE COMMIT COMMAND CENTER',
        'AURON TELEGRAM RETRY CONTROLLER COMMAND CENTER',
    )
    return html
