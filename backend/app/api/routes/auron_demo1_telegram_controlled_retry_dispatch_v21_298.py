from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_delivery_state_commit_v21_296 import _commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider, _outbound_store
from app.api.routes.auron_demo1_telegram_retry_controller_v21_297 import _retry_store

router = APIRouter(prefix='/auron/demo1/v21.298', tags=['auron-demo1-telegram-controlled-retry-dispatch'])

_retry_dispatch_store: dict[str, dict] = {}


class TelegramRetryDispatchRequest(BaseModel):
    retry_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    force_eligible: bool = False
    dry_run: bool = True


def reset_telegram_controlled_retry_dispatch_store() -> None:
    _retry_dispatch_store.clear()


def _retry_by_id(retry_id: str) -> dict | None:
    return next((item for item in _retry_store.values() if item['retry_id'] == retry_id), None)


@router.get('/status')
def telegram_retry_dispatch_status() -> dict:
    return {
        'prepared_retry_dispatches': len(_retry_dispatch_store),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'dispatch_mode': 'controlled-dry-run-retry-dispatch',
    }


@router.post('/dispatch')
def dispatch_telegram_retry(payload: TelegramRetryDispatchRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram retry dispatch is not enabled in v21.298')

    existing = _retry_dispatch_store.get(payload.retry_id)
    if existing is not None:
        return {
            'state': 'telegram-retry-dispatch-already-prepared',
            'retry_dispatch': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    retry = _retry_by_id(payload.retry_id)
    if retry is None:
        raise HTTPException(status_code=404, detail='Scheduled Telegram retry not found')
    if retry.get('retry_state') != 'scheduled':
        raise HTTPException(status_code=409, detail='Telegram retry is not in scheduled state')

    commit = _commit_store.get(retry['correlation_id'])
    outbound = _outbound_store.get(retry['correlation_id'])
    provider = _active_provider()
    if commit is None or outbound is None:
        raise HTTPException(status_code=409, detail='Correlated Telegram retry chain required')
    if provider is None or not provider.get('provider_ready'):
        raise HTTPException(status_code=409, detail='Ready Telegram provider required')
    if commit.get('terminal') is True or commit.get('delivery_state') != 'retry-scheduled':
        raise HTTPException(status_code=409, detail='Retry commit is no longer dispatchable')
    if retry['attempt'] > retry['max_attempts']:
        raise HTTPException(status_code=409, detail='Telegram retry attempt budget exceeded')

    now = datetime.now(timezone.utc)
    eligible_at = datetime.fromisoformat(retry['eligible_at'])
    if eligible_at.tzinfo is None:
        eligible_at = eligible_at.replace(tzinfo=timezone.utc)
    if now < eligible_at and not payload.force_eligible:
        return {
            'state': 'telegram-retry-dispatch-not-yet-eligible',
            'retry_id': retry['retry_id'],
            'eligible_at': retry['eligible_at'],
            'provider_api_calls_made': 0,
            'outbound_messages_sent': 0,
            'external_calls_made': 0,
        }

    retry_dispatch_id = str(uuid4())
    record = {
        'retry_dispatch_id': retry_dispatch_id,
        'retry_id': retry['retry_id'],
        'correlation_id': retry['correlation_id'],
        'delivery_commit_id': retry['delivery_commit_id'],
        'outbound_id': outbound['outbound_id'],
        'provider_id': provider['provider_id'],
        'runtime_id': provider['runtime_id'],
        'attempt': retry['attempt'],
        'max_attempts': retry['max_attempts'],
        'telegram_chat_id': outbound.get('telegram_chat_id'),
        'text': outbound.get('text'),
        'reply_to_message_id': outbound.get('reply_to_message_id'),
        'dispatch_state': 'prepared-not-called',
        'provider_call_performed': False,
        'message_sent': False,
        'prepared_by': payload.actor,
        'prepared_at': now.isoformat(),
    }
    _retry_dispatch_store[payload.retry_id] = record
    retry['retry_state'] = 'dispatch-prepared'
    retry['retry_dispatch_id'] = retry_dispatch_id
    commit['attempt'] = retry['attempt']
    commit['active_retry_dispatch_id'] = retry_dispatch_id
    outbound['delivery_state'] = 'retry-dispatch-prepared'
    outbound['retry_dispatch_id'] = retry_dispatch_id

    return {
        'state': 'telegram-retry-dispatch-prepared',
        'retry_dispatch': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-retry-provider-call-boundary',
        'reply': 'Telegram-Retry-Dispatch wurde kontrolliert vorbereitet. Noch wurde kein Provider aufgerufen.',
    }


@router.get('/dispatches')
def list_telegram_retry_dispatches() -> dict:
    items = sorted(_retry_dispatch_store.values(), key=lambda item: item['prepared_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_retry_controller_v21_297 import command_center as v21_297_command_center

    html = v21_297_command_center()
    html = html.replace('v21.297', 'v21.298')
    html = html.replace(
        'AURON TELEGRAM RETRY CONTROLLER COMMAND CENTER',
        'AURON TELEGRAM CONTROLLED RETRY DISPATCH COMMAND CENTER',
    )
    return html
