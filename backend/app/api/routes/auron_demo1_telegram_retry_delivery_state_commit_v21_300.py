from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_retry_dispatch_v21_298 import _retry_dispatch_store
from app.api.routes.auron_demo1_telegram_delivery_state_commit_v21_296 import _commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store
from app.api.routes.auron_demo1_telegram_retry_controller_v21_297 import _retry_store
from app.api.routes.auron_demo1_telegram_retry_provider_call_boundary_v21_299 import (
    _retry_call_store,
    _retry_receipt_store,
)

router = APIRouter(prefix='/auron/demo1/v21.300', tags=['auron-demo1-telegram-retry-delivery-state-commit'])

_retry_delivery_commit_store: dict[str, dict] = {}


class TelegramRetryDeliveryCommitRequest(BaseModel):
    retry_dispatch_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)


def reset_telegram_retry_delivery_state_commit_store() -> None:
    _retry_delivery_commit_store.clear()


def _classify_rejection(error: str | None) -> str:
    value = (error or '').lower()
    if any(token in value for token in ('timeout', 'temporar', 'rate limit', '429', 'unavailable', 'network')):
        return 'retryable'
    return 'permanent'


def _dispatch_by_id(retry_dispatch_id: str) -> dict | None:
    return next((item for item in _retry_dispatch_store.values() if item['retry_dispatch_id'] == retry_dispatch_id), None)


def _retry_by_id(retry_id: str) -> dict | None:
    return next((item for item in _retry_store.values() if item['retry_id'] == retry_id), None)


@router.get('/status')
def telegram_retry_delivery_commit_status() -> dict:
    delivered = sum(1 for item in _retry_delivery_commit_store.values() if item['delivery_state'] == 'delivered')
    retry_scheduled = sum(1 for item in _retry_delivery_commit_store.values() if item['delivery_state'] == 'retry-scheduled')
    terminal_failures = sum(1 for item in _retry_delivery_commit_store.values() if item['terminal'] and item['delivery_state'] != 'delivered')
    return {
        'retry_delivery_commits': len(_retry_delivery_commit_store),
        'delivered': delivered,
        'retry_scheduled': retry_scheduled,
        'terminal_failures': terminal_failures,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'commit_mode': 'verified-retry-receipt-state-commit',
    }


@router.post('/commit')
def commit_telegram_retry_delivery(payload: TelegramRetryDeliveryCommitRequest) -> dict:
    existing = _retry_delivery_commit_store.get(payload.retry_dispatch_id)
    if existing is not None:
        return {
            'state': 'telegram-retry-delivery-already-committed',
            'commit': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    receipt = _retry_receipt_store.get(payload.retry_dispatch_id)
    call = _retry_call_store.get(payload.retry_dispatch_id)
    dispatch = _dispatch_by_id(payload.retry_dispatch_id)
    if not all((receipt, call, dispatch)):
        raise HTTPException(status_code=409, detail='Complete correlated Telegram retry delivery chain required')
    if receipt['retry_call_id'] != call['retry_call_id'] or call['retry_dispatch_id'] != dispatch['retry_dispatch_id']:
        raise HTTPException(status_code=409, detail='Telegram retry delivery chain correlation mismatch')

    retry = _retry_by_id(dispatch['retry_id'])
    original_commit = _commit_store.get(dispatch['correlation_id'])
    outbound = _outbound_store.get(dispatch['correlation_id'])
    if not all((retry, original_commit, outbound)):
        raise HTTPException(status_code=409, detail='Telegram retry state chain is incomplete')

    accepted = receipt['accepted']
    rejection_class = None if accepted else _classify_rejection(receipt.get('provider_error'))
    attempt = int(receipt['attempt'])
    max_attempts = int(call['max_attempts'])
    if accepted:
        delivery_state = 'delivered'
        terminal = True
        next_layer = 'telegram-terminal-delivery-audit'
    elif rejection_class == 'retryable' and attempt < max_attempts:
        delivery_state = 'retry-scheduled'
        terminal = False
        next_layer = 'telegram-send-retry-controller'
    elif rejection_class == 'retryable':
        delivery_state = 'retry-exhausted'
        terminal = True
        next_layer = 'telegram-terminal-delivery-audit'
    else:
        delivery_state = 'permanent-failure'
        terminal = True
        next_layer = 'telegram-terminal-delivery-audit'

    now = datetime.now(timezone.utc).isoformat()
    record = {
        'retry_delivery_commit_id': str(uuid4()),
        'retry_dispatch_id': payload.retry_dispatch_id,
        'retry_receipt_id': receipt['retry_receipt_id'],
        'retry_call_id': call['retry_call_id'],
        'retry_id': dispatch['retry_id'],
        'correlation_id': dispatch['correlation_id'],
        'delivery_commit_id': dispatch['delivery_commit_id'],
        'outbound_id': dispatch['outbound_id'],
        'provider_message_id': receipt.get('provider_message_id'),
        'provider_error': receipt.get('provider_error'),
        'rejection_class': rejection_class,
        'attempt': attempt,
        'max_attempts': max_attempts,
        'delivery_state': delivery_state,
        'terminal': terminal,
        'committed_by': payload.actor,
        'committed_at': now,
    }
    _retry_delivery_commit_store[payload.retry_dispatch_id] = record

    dispatch['dispatch_state'] = 'retry-delivery-committed'
    retry['retry_state'] = 'completed' if terminal else 'retry-required'
    retry['retry_delivery_commit_id'] = record['retry_delivery_commit_id']
    original_commit['attempt'] = attempt
    original_commit['delivery_state'] = delivery_state
    original_commit['terminal'] = terminal
    original_commit['latest_retry_delivery_commit_id'] = record['retry_delivery_commit_id']
    original_commit['provider_message_id'] = receipt.get('provider_message_id')
    original_commit['provider_error'] = receipt.get('provider_error')
    outbound['delivery_state'] = delivery_state
    outbound['provider_message_id'] = receipt.get('provider_message_id')
    outbound['latest_retry_delivery_commit_id'] = record['retry_delivery_commit_id']

    return {
        'state': 'telegram-retry-delivery-state-committed',
        'commit': record,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'next_layer': next_layer,
    }


@router.get('/commits')
def list_retry_delivery_commits() -> dict:
    items = sorted(_retry_delivery_commit_store.values(), key=lambda item: item['committed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_retry_provider_call_boundary_v21_299 import command_center as v21_299_command_center

    html = v21_299_command_center()
    html = html.replace('v21.299', 'v21.300')
    html = html.replace(
        'AURON TELEGRAM RETRY PROVIDER CALL BOUNDARY COMMAND CENTER',
        'AURON TELEGRAM RETRY DELIVERY STATE COMMIT COMMAND CENTER',
    )
    return html
