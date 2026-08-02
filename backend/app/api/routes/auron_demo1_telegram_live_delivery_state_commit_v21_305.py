from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_live_transport_adapter_v21_304 import (
    _live_execution_store,
    _live_receipt_store,
)
from app.api.routes.auron_demo1_telegram_controlled_send_adapter_v21_294 import _dispatch_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.305', tags=['auron-demo1-telegram-live-delivery-state-commit'])

_live_delivery_commit_store: dict[str, dict] = {}


class TelegramLiveDeliveryCommitRequest(BaseModel):
    execution_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)


def reset_telegram_live_delivery_state_commit_store() -> None:
    _live_delivery_commit_store.clear()


def _execution_by_id(execution_id: str) -> dict | None:
    return next((item for item in _live_execution_store.values() if item['execution_id'] == execution_id), None)


def _classify_failure(error: str | None, http_status: int) -> str:
    value = (error or '').lower()
    if http_status == 429 or http_status >= 500 or any(token in value for token in ('timeout', 'temporar', 'network', 'unavailable', 'rate limit')):
        return 'retryable'
    return 'permanent'


@router.get('/status')
def telegram_live_delivery_commit_status() -> dict:
    return {
        'live_delivery_commits': len(_live_delivery_commit_store),
        'delivered': sum(1 for item in _live_delivery_commit_store.values() if item['delivery_state'] == 'delivered'),
        'retry_required': sum(1 for item in _live_delivery_commit_store.values() if item['delivery_state'] == 'retry-required'),
        'permanent_failures': sum(1 for item in _live_delivery_commit_store.values() if item['delivery_state'] == 'permanent-failure'),
        'external_calls_made': 0,
        'commit_mode': 'captured-live-provider-receipt-commit',
    }


@router.post('/commit')
def commit_live_delivery(payload: TelegramLiveDeliveryCommitRequest) -> dict:
    existing = _live_delivery_commit_store.get(payload.execution_id)
    if existing is not None:
        return {
            'state': 'telegram-live-delivery-already-committed',
            'commit': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    execution = _execution_by_id(payload.execution_id)
    receipt = _live_receipt_store.get(payload.execution_id)
    if execution is None or receipt is None:
        raise HTTPException(status_code=409, detail='Captured Telegram live execution and provider receipt required')
    if receipt.get('execution_id') != execution.get('execution_id') or receipt.get('correlation_id') != execution.get('correlation_id'):
        raise HTTPException(status_code=409, detail='Telegram live delivery correlation mismatch')
    if execution.get('execution_state') != 'provider-receipt-captured':
        raise HTTPException(status_code=409, detail='Telegram live provider receipt has not been captured')

    outbound = _outbound_store.get(execution['correlation_id'])
    dispatch = _dispatch_store.get(execution['correlation_id'])
    if outbound is None or dispatch is None:
        raise HTTPException(status_code=409, detail='Correlated Telegram outbound and dispatch required')
    if outbound.get('outbound_id') != execution.get('outbound_id') or dispatch.get('dispatch_id') != execution.get('dispatch_id'):
        raise HTTPException(status_code=409, detail='Telegram live execution chain mismatch')

    accepted = receipt['accepted']
    failure_class = None if accepted else _classify_failure(receipt.get('provider_error'), receipt['http_status'])
    if accepted:
        delivery_state = 'delivered'
        terminal = True
        next_layer = 'telegram-live-terminal-audit'
    elif failure_class == 'retryable':
        delivery_state = 'retry-required'
        terminal = False
        next_layer = 'telegram-live-retry-controller'
    else:
        delivery_state = 'permanent-failure'
        terminal = True
        next_layer = 'telegram-live-terminal-audit'

    now = datetime.now(timezone.utc).isoformat()
    record = {
        'live_delivery_commit_id': str(uuid4()),
        'execution_id': payload.execution_id,
        'receipt_id': receipt['receipt_id'],
        'correlation_id': execution['correlation_id'],
        'activation_id': execution['activation_id'],
        'provider_id': execution['provider_id'],
        'runtime_id': execution['runtime_id'],
        'outbound_id': execution['outbound_id'],
        'dispatch_id': execution['dispatch_id'],
        'accepted': accepted,
        'provider_message_id': receipt.get('provider_message_id'),
        'provider_error': receipt.get('provider_error'),
        'http_status': receipt['http_status'],
        'failure_class': failure_class,
        'delivery_state': delivery_state,
        'terminal': terminal,
        'committed_by': payload.actor,
        'committed_at': now,
    }
    _live_delivery_commit_store[payload.execution_id] = record
    execution['execution_state'] = 'delivery-committed'
    execution['live_delivery_commit_id'] = record['live_delivery_commit_id']
    dispatch['dispatch_state'] = 'delivery-committed'
    dispatch['live_delivery_commit_id'] = record['live_delivery_commit_id']
    outbound['delivery_state'] = delivery_state
    outbound['provider_message_id'] = receipt.get('provider_message_id')
    outbound['provider_error'] = receipt.get('provider_error')
    outbound['live_delivery_commit_id'] = record['live_delivery_commit_id']

    return {
        'state': 'telegram-live-delivery-state-committed',
        'commit': record,
        'external_calls_made': 0,
        'next_layer': next_layer,
    }


@router.get('/commits')
def list_live_delivery_commits() -> dict:
    items = sorted(_live_delivery_commit_store.values(), key=lambda item: item['committed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_controlled_live_transport_adapter_v21_304 import command_center as v21_304_command_center

    html = v21_304_command_center()
    html = html.replace('v21.304', 'v21.305')
    html = html.replace(
        'AURON TELEGRAM CONTROLLED LIVE TRANSPORT ADAPTER COMMAND CENTER',
        'AURON TELEGRAM LIVE DELIVERY STATE COMMIT COMMAND CENTER',
    )
    return html
