from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_send_adapter_v21_294 import _dispatch_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider, _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.295', tags=['auron-demo1-telegram-provider-call-boundary'])

_call_store: dict[str, dict] = {}
_receipt_store: dict[str, dict] = {}


class TelegramProviderCallRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    dry_run: bool = True


class TelegramProviderReceiptRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    accepted: bool
    provider_message_id: str | None = Field(default=None, max_length=160)
    provider_error: str | None = Field(default=None, max_length=500)


def reset_telegram_provider_call_boundary_store() -> None:
    _call_store.clear()
    _receipt_store.clear()


@router.get('/status')
def provider_call_boundary_status() -> dict:
    return {
        'prepared_provider_calls': len(_call_store),
        'verified_receipts': len(_receipt_store),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'boundary_mode': 'provider-call-contract-and-receipt-verification',
    }


@router.post('/prepare-call')
def prepare_provider_call(payload: TelegramProviderCallRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram provider call is not enabled in v21.295')
    existing = _call_store.get(payload.correlation_id)
    if existing is not None:
        return {'state': 'telegram-provider-call-already-prepared', 'call': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    dispatch = _dispatch_store.get(payload.correlation_id)
    if dispatch is None:
        raise HTTPException(status_code=404, detail='Telegram send dispatch not found')
    if dispatch.get('dispatch_state') != 'prepared-not-called':
        raise HTTPException(status_code=409, detail='Telegram send dispatch is not callable')
    provider = _active_provider()
    if provider is None or not provider.get('provider_ready'):
        raise HTTPException(status_code=409, detail='Ready Telegram provider required')
    outbound = _outbound_store.get(payload.correlation_id)
    if outbound is None or outbound.get('dispatch_id') != dispatch['dispatch_id']:
        raise HTTPException(status_code=409, detail='Correlated Telegram outbound envelope required')

    call_id = str(uuid4())
    record = {
        'call_id': call_id,
        'correlation_id': payload.correlation_id,
        'dispatch_id': dispatch['dispatch_id'],
        'outbound_id': outbound['outbound_id'],
        'provider_id': provider['provider_id'],
        'runtime_id': provider['runtime_id'],
        'method': 'sendMessage',
        'request_body': {
            'chat_id': outbound['telegram_chat_id'],
            'text': outbound['text'],
            'reply_to_message_id': outbound['reply_to_message_id'],
            'parse_mode': outbound['parse_mode'],
            'disable_notification': outbound['disable_notification'],
        },
        'call_state': 'prepared-not-executed',
        'provider_call_performed': False,
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
    }
    _call_store[payload.correlation_id] = record
    dispatch['dispatch_state'] = 'provider-call-prepared'
    dispatch['call_id'] = call_id
    return {
        'state': 'telegram-provider-call-prepared',
        'call': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-provider-call-execution',
        'reply': 'Telegram Bot API Aufruf ist vollständig vorbereitet, aber noch nicht ausgeführt.',
    }


@router.post('/verify-receipt')
def verify_provider_receipt(payload: TelegramProviderReceiptRequest) -> dict:
    call = _call_store.get(payload.correlation_id)
    if call is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram provider call not found')
    existing = _receipt_store.get(payload.correlation_id)
    if existing is not None:
        return {'state': 'telegram-provider-receipt-already-verified', 'receipt': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if payload.accepted and not payload.provider_message_id:
        raise HTTPException(status_code=422, detail='Accepted provider receipt requires provider_message_id')
    if not payload.accepted and not payload.provider_error:
        raise HTTPException(status_code=422, detail='Rejected provider receipt requires provider_error')

    receipt = {
        'receipt_id': str(uuid4()),
        'correlation_id': payload.correlation_id,
        'call_id': call['call_id'],
        'dispatch_id': call['dispatch_id'],
        'accepted': payload.accepted,
        'provider_message_id': payload.provider_message_id,
        'provider_error': payload.provider_error,
        'verification_state': 'accepted-awaiting-delivery-commit' if payload.accepted else 'rejected-awaiting-retry-classification',
        'verified_at': datetime.now(timezone.utc).isoformat(),
    }
    _receipt_store[payload.correlation_id] = receipt
    call['receipt_verified'] = True
    call['receipt_id'] = receipt['receipt_id']
    return {
        'state': 'telegram-provider-receipt-verified',
        'receipt': receipt,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-delivery-state-commit' if payload.accepted else 'telegram-send-retry-classification',
    }


@router.get('/calls')
def list_provider_calls() -> dict:
    return {'count': len(_call_store), 'items': list(_call_store.values()), 'external_calls_made': 0}


@router.get('/receipts')
def list_provider_receipts() -> dict:
    return {'count': len(_receipt_store), 'items': list(_receipt_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_controlled_send_adapter_v21_294 import command_center as v21_294_command_center
    html = v21_294_command_center()
    html = html.replace('v21.294', 'v21.295')
    html = html.replace('AURON TELEGRAM CONTROLLED SEND ADAPTER COMMAND CENTER', 'AURON TELEGRAM PROVIDER CALL BOUNDARY COMMAND CENTER')
    return html
