from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_live_controlled_retry_dispatch_v21_307 import _live_retry_dispatch_store
from app.api.routes.auron_demo1_telegram_live_retry_controller_v21_306 import _live_retry_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.308', tags=['auron-demo1-telegram-live-retry-receipt-commit'])

_live_retry_receipt_store: dict[str, dict] = {}
_live_retry_commit_store: dict[str, dict] = {}


class TelegramLiveRetryReceiptRequest(BaseModel):
    live_retry_dispatch_id: str = Field(min_length=1, max_length=160)
    accepted: bool
    provider_message_id: str | None = Field(default=None, max_length=160)
    provider_error: str | None = Field(default=None, max_length=500)
    http_status: int = Field(ge=100, le=599)


class TelegramLiveRetryCommitRequest(BaseModel):
    live_retry_dispatch_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)


def reset_telegram_live_retry_receipt_commit_store() -> None:
    _live_retry_receipt_store.clear()
    _live_retry_commit_store.clear()


def _dispatch_by_id(dispatch_id: str) -> dict | None:
    return next((item for item in _live_retry_dispatch_store.values() if item['live_retry_dispatch_id'] == dispatch_id), None)


def _classify_failure(error: str | None, http_status: int) -> str:
    value = (error or '').lower()
    if http_status == 429 or http_status >= 500 or any(token in value for token in ('timeout', 'temporar', 'network', 'unavailable', 'rate limit')):
        return 'retryable'
    return 'permanent'


@router.get('/status')
def telegram_live_retry_receipt_commit_status() -> dict:
    return {
        'captured_retry_receipts': len(_live_retry_receipt_store),
        'retry_delivery_commits': len(_live_retry_commit_store),
        'delivered': sum(1 for item in _live_retry_commit_store.values() if item['delivery_state'] == 'delivered'),
        'retry_required': sum(1 for item in _live_retry_commit_store.values() if item['delivery_state'] == 'retry-required'),
        'terminal_failures': sum(1 for item in _live_retry_commit_store.values() if item['terminal'] and item['delivery_state'] != 'delivered'),
        'external_calls_made': 0,
        'commit_mode': 'captured-live-retry-provider-receipt-commit',
    }


@router.post('/capture-receipt')
def capture_live_retry_receipt(payload: TelegramLiveRetryReceiptRequest) -> dict:
    dispatch = _dispatch_by_id(payload.live_retry_dispatch_id)
    if dispatch is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram live retry dispatch not found')
    existing = _live_retry_receipt_store.get(payload.live_retry_dispatch_id)
    if existing is not None:
        return {'state': 'telegram-live-retry-receipt-already-captured', 'receipt': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if payload.accepted and not payload.provider_message_id:
        raise HTTPException(status_code=422, detail='Accepted Telegram retry receipt requires provider_message_id')
    if not payload.accepted and not payload.provider_error:
        raise HTTPException(status_code=422, detail='Rejected Telegram retry receipt requires provider_error')

    receipt = {
        'live_retry_receipt_id': str(uuid4()),
        'live_retry_dispatch_id': payload.live_retry_dispatch_id,
        'live_retry_id': dispatch['live_retry_id'],
        'correlation_id': dispatch['correlation_id'],
        'attempt': dispatch['attempt'],
        'accepted': payload.accepted,
        'provider_message_id': payload.provider_message_id,
        'provider_error': payload.provider_error,
        'http_status': payload.http_status,
        'captured_at': datetime.now(timezone.utc).isoformat(),
    }
    _live_retry_receipt_store[payload.live_retry_dispatch_id] = receipt
    dispatch['dispatch_state'] = 'provider-receipt-captured'
    dispatch['provider_call_performed'] = True
    dispatch['message_sent'] = payload.accepted
    dispatch['live_retry_receipt_id'] = receipt['live_retry_receipt_id']
    return {'state': 'telegram-live-retry-receipt-captured', 'receipt': receipt, 'external_calls_made': 0, 'next_layer': 'telegram-live-retry-delivery-state-commit'}


@router.post('/commit')
def commit_live_retry_delivery(payload: TelegramLiveRetryCommitRequest) -> dict:
    existing = _live_retry_commit_store.get(payload.live_retry_dispatch_id)
    if existing is not None:
        return {'state': 'telegram-live-retry-delivery-already-committed', 'commit': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    dispatch = _dispatch_by_id(payload.live_retry_dispatch_id)
    receipt = _live_retry_receipt_store.get(payload.live_retry_dispatch_id)
    if dispatch is None or receipt is None:
        raise HTTPException(status_code=409, detail='Captured Telegram live retry dispatch and receipt required')
    retry = next((item for item in _live_retry_store.values() if item['live_retry_id'] == dispatch['live_retry_id']), None)
    outbound = _outbound_store.get(dispatch['correlation_id'])
    if retry is None or outbound is None:
        raise HTTPException(status_code=409, detail='Correlated Telegram live retry and outbound required')
    if receipt['live_retry_id'] != retry['live_retry_id'] or outbound.get('outbound_id') != dispatch.get('outbound_id'):
        raise HTTPException(status_code=409, detail='Telegram live retry delivery correlation mismatch')

    accepted = receipt['accepted']
    failure_class = None if accepted else _classify_failure(receipt.get('provider_error'), receipt['http_status'])
    if accepted:
        delivery_state, terminal, next_layer = 'delivered', True, 'telegram-live-terminal-audit'
    elif failure_class == 'retryable' and dispatch['attempt'] < dispatch['max_attempts']:
        delivery_state, terminal, next_layer = 'retry-required', False, 'telegram-live-retry-controller'
    elif failure_class == 'retryable':
        delivery_state, terminal, next_layer = 'retry-exhausted', True, 'telegram-live-terminal-audit'
    else:
        delivery_state, terminal, next_layer = 'permanent-failure', True, 'telegram-live-terminal-audit'

    record = {
        'live_retry_delivery_commit_id': str(uuid4()),
        'live_retry_dispatch_id': payload.live_retry_dispatch_id,
        'live_retry_receipt_id': receipt['live_retry_receipt_id'],
        'live_retry_id': retry['live_retry_id'],
        'live_delivery_commit_id': retry['live_delivery_commit_id'],
        'correlation_id': dispatch['correlation_id'],
        'provider_id': dispatch['provider_id'],
        'runtime_id': dispatch['runtime_id'],
        'outbound_id': dispatch['outbound_id'],
        'attempt': dispatch['attempt'],
        'max_attempts': dispatch['max_attempts'],
        'accepted': accepted,
        'provider_message_id': receipt.get('provider_message_id'),
        'provider_error': receipt.get('provider_error'),
        'http_status': receipt['http_status'],
        'failure_class': failure_class,
        'delivery_state': delivery_state,
        'terminal': terminal,
        'committed_by': payload.actor,
        'committed_at': datetime.now(timezone.utc).isoformat(),
    }
    _live_retry_commit_store[payload.live_retry_dispatch_id] = record
    dispatch['dispatch_state'] = 'delivery-committed'
    dispatch['live_retry_delivery_commit_id'] = record['live_retry_delivery_commit_id']
    retry['retry_state'] = delivery_state
    retry['terminal'] = terminal
    retry['live_retry_delivery_commit_id'] = record['live_retry_delivery_commit_id']
    outbound['delivery_state'] = delivery_state
    outbound['provider_message_id'] = receipt.get('provider_message_id')
    outbound['provider_error'] = receipt.get('provider_error')
    outbound['live_retry_delivery_commit_id'] = record['live_retry_delivery_commit_id']
    return {'state': 'telegram-live-retry-delivery-state-committed', 'commit': record, 'external_calls_made': 0, 'next_layer': next_layer}


@router.get('/receipts')
def list_live_retry_receipts() -> dict:
    return {'count': len(_live_retry_receipt_store), 'items': list(_live_retry_receipt_store.values()), 'external_calls_made': 0}


@router.get('/commits')
def list_live_retry_commits() -> dict:
    return {'count': len(_live_retry_commit_store), 'items': list(_live_retry_commit_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_live_controlled_retry_dispatch_v21_307 import command_center as v21_307_command_center
    html = v21_307_command_center()
    html = html.replace('v21.307', 'v21.308')
    return html.replace('AURON TELEGRAM LIVE CONTROLLED RETRY DISPATCH COMMAND CENTER', 'AURON TELEGRAM LIVE RETRY RECEIPT COMMIT COMMAND CENTER')
