from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_send_adapter_v21_294 import _dispatch_store
from app.api.routes.auron_demo1_telegram_conversation_router_v21_293 import _conversation_store
from app.api.routes.auron_demo1_telegram_provider_call_boundary_v21_295 import _call_store, _receipt_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.296', tags=['auron-demo1-telegram-delivery-state-commit'])

_commit_store: dict[str, dict] = {}


class TelegramDeliveryCommitRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    max_attempts: int = Field(default=3, ge=1, le=10)


def reset_telegram_delivery_state_commit_store() -> None:
    _commit_store.clear()


def _classify_rejection(error: str | None) -> str:
    value = (error or '').lower()
    if any(token in value for token in ('timeout', 'temporar', 'rate limit', '429', 'unavailable', 'network')):
        return 'retryable'
    return 'permanent'


@router.get('/status')
def telegram_delivery_commit_status() -> dict:
    delivered = sum(1 for item in _commit_store.values() if item['delivery_state'] == 'delivered')
    retryable = sum(1 for item in _commit_store.values() if item['delivery_state'] == 'retry-scheduled')
    return {
        'delivery_commits': len(_commit_store),
        'delivered': delivered,
        'retry_scheduled': retryable,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'commit_mode': 'verified-receipt-state-commit',
    }


@router.post('/commit')
def commit_telegram_delivery(payload: TelegramDeliveryCommitRequest) -> dict:
    existing = _commit_store.get(payload.correlation_id)
    if existing is not None:
        return {'state': 'telegram-delivery-already-committed', 'commit': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    receipt = _receipt_store.get(payload.correlation_id)
    call = _call_store.get(payload.correlation_id)
    dispatch = _dispatch_store.get(payload.correlation_id)
    outbound = _outbound_store.get(payload.correlation_id)
    conversation = next((item for item in _conversation_store.values() if item['correlation_id'] == payload.correlation_id), None)
    if not all((receipt, call, dispatch, outbound, conversation)):
        raise HTTPException(status_code=409, detail='Complete correlated Telegram delivery chain required')
    if receipt['call_id'] != call['call_id'] or call['dispatch_id'] != dispatch['dispatch_id']:
        raise HTTPException(status_code=409, detail='Telegram delivery chain correlation mismatch')

    accepted = receipt['accepted']
    rejection_class = None if accepted else _classify_rejection(receipt.get('provider_error'))
    if accepted:
        delivery_state = 'delivered'
        terminal = True
        next_layer = 'telegram-delivery-audit'
    elif rejection_class == 'retryable':
        delivery_state = 'retry-scheduled'
        terminal = False
        next_layer = 'telegram-send-retry-controller'
    else:
        delivery_state = 'permanent-failure'
        terminal = True
        next_layer = 'telegram-delivery-audit'

    now = datetime.now(timezone.utc).isoformat()
    record = {
        'commit_id': str(uuid4()),
        'correlation_id': payload.correlation_id,
        'receipt_id': receipt['receipt_id'],
        'call_id': call['call_id'],
        'dispatch_id': dispatch['dispatch_id'],
        'outbound_id': outbound['outbound_id'],
        'conversation_id': conversation['conversation_id'],
        'provider_message_id': receipt.get('provider_message_id'),
        'provider_error': receipt.get('provider_error'),
        'rejection_class': rejection_class,
        'delivery_state': delivery_state,
        'terminal': terminal,
        'attempt': 1,
        'max_attempts': payload.max_attempts,
        'committed_by': payload.actor,
        'committed_at': now,
    }
    _commit_store[payload.correlation_id] = record
    outbound['delivery_state'] = delivery_state
    outbound['delivery_commit_id'] = record['commit_id']
    outbound['provider_message_id'] = receipt.get('provider_message_id')
    dispatch['dispatch_state'] = 'delivery-committed'
    conversation['reply_sent'] = accepted

    return {
        'state': 'telegram-delivery-state-committed',
        'commit': record,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'next_layer': next_layer,
    }


@router.get('/commits')
def list_delivery_commits() -> dict:
    items = sorted(_commit_store.values(), key=lambda item: item['committed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_provider_call_boundary_v21_295 import command_center as v21_295_command_center
    html = v21_295_command_center()
    html = html.replace('v21.295', 'v21.296')
    html = html.replace('AURON TELEGRAM PROVIDER CALL BOUNDARY COMMAND CENTER', 'AURON TELEGRAM DELIVERY STATE COMMIT COMMAND CENTER')
    return html
