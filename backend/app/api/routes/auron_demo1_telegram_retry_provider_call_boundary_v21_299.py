from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_retry_dispatch_v21_298 import _retry_dispatch_store
from app.api.routes.auron_demo1_telegram_retry_controller_v21_297 import _retry_store

router = APIRouter(prefix='/auron/demo1/v21.299', tags=['auron-demo1-telegram-retry-provider-call-boundary'])

_retry_call_store: dict[str, dict] = {}
_retry_receipt_store: dict[str, dict] = {}


class TelegramRetryProviderCallRequest(BaseModel):
    retry_dispatch_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    dry_run: bool = True


class TelegramRetryProviderReceiptRequest(BaseModel):
    retry_dispatch_id: str = Field(min_length=1, max_length=160)
    accepted: bool
    provider_message_id: str | None = Field(default=None, max_length=160)
    provider_error: str | None = Field(default=None, max_length=500)


def reset_telegram_retry_provider_call_boundary_store() -> None:
    _retry_call_store.clear()
    _retry_receipt_store.clear()


def _dispatch_by_id(retry_dispatch_id: str) -> dict | None:
    return next((item for item in _retry_dispatch_store.values() if item['retry_dispatch_id'] == retry_dispatch_id), None)


def _retry_by_id(retry_id: str) -> dict | None:
    return next((item for item in _retry_store.values() if item['retry_id'] == retry_id), None)


@router.get('/status')
def telegram_retry_provider_status() -> dict:
    return {
        'prepared_retry_calls': len(_retry_call_store),
        'verified_retry_receipts': len(_retry_receipt_store),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'boundary_mode': 'retry-provider-call-contract-and-receipt-verification',
    }


@router.post('/prepare-call')
def prepare_retry_provider_call(payload: TelegramRetryProviderCallRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram retry provider call is not enabled in v21.299')
    existing = _retry_call_store.get(payload.retry_dispatch_id)
    if existing is not None:
        return {'state': 'telegram-retry-provider-call-already-prepared', 'call': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    dispatch = _dispatch_by_id(payload.retry_dispatch_id)
    if dispatch is None:
        raise HTTPException(status_code=404, detail='Telegram retry dispatch not found')
    if dispatch.get('dispatch_state') != 'prepared-not-called':
        raise HTTPException(status_code=409, detail='Telegram retry dispatch is not callable')
    retry = _retry_by_id(dispatch['retry_id'])
    if retry is None or retry.get('retry_state') != 'dispatch-prepared':
        raise HTTPException(status_code=409, detail='Correlated dispatch-prepared Telegram retry required')
    if dispatch['attempt'] > dispatch['max_attempts']:
        raise HTTPException(status_code=409, detail='Telegram retry attempt budget exceeded')

    call_id = str(uuid4())
    record = {
        'retry_call_id': call_id,
        'retry_dispatch_id': dispatch['retry_dispatch_id'],
        'retry_id': dispatch['retry_id'],
        'correlation_id': dispatch['correlation_id'],
        'delivery_commit_id': dispatch['delivery_commit_id'],
        'provider_id': dispatch['provider_id'],
        'runtime_id': dispatch['runtime_id'],
        'attempt': dispatch['attempt'],
        'max_attempts': dispatch['max_attempts'],
        'method': 'sendMessage',
        'request_body': {
            'chat_id': dispatch['telegram_chat_id'],
            'text': dispatch['text'],
            'reply_to_message_id': dispatch['reply_to_message_id'],
        },
        'call_state': 'prepared-not-executed',
        'provider_call_performed': False,
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
    }
    _retry_call_store[payload.retry_dispatch_id] = record
    dispatch['dispatch_state'] = 'provider-call-prepared'
    dispatch['retry_call_id'] = call_id
    retry['retry_state'] = 'provider-call-prepared'
    return {
        'state': 'telegram-retry-provider-call-prepared',
        'call': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-retry-provider-execution',
    }


@router.post('/verify-receipt')
def verify_retry_provider_receipt(payload: TelegramRetryProviderReceiptRequest) -> dict:
    call = _retry_call_store.get(payload.retry_dispatch_id)
    if call is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram retry provider call not found')
    existing = _retry_receipt_store.get(payload.retry_dispatch_id)
    if existing is not None:
        return {'state': 'telegram-retry-provider-receipt-already-verified', 'receipt': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if payload.accepted and not payload.provider_message_id:
        raise HTTPException(status_code=422, detail='Accepted retry receipt requires provider_message_id')
    if not payload.accepted and not payload.provider_error:
        raise HTTPException(status_code=422, detail='Rejected retry receipt requires provider_error')

    receipt = {
        'retry_receipt_id': str(uuid4()),
        'retry_dispatch_id': payload.retry_dispatch_id,
        'retry_call_id': call['retry_call_id'],
        'retry_id': call['retry_id'],
        'correlation_id': call['correlation_id'],
        'attempt': call['attempt'],
        'accepted': payload.accepted,
        'provider_message_id': payload.provider_message_id,
        'provider_error': payload.provider_error,
        'verification_state': 'accepted-awaiting-retry-delivery-commit' if payload.accepted else 'rejected-awaiting-retry-classification',
        'verified_at': datetime.now(timezone.utc).isoformat(),
    }
    _retry_receipt_store[payload.retry_dispatch_id] = receipt
    call['receipt_verified'] = True
    call['retry_receipt_id'] = receipt['retry_receipt_id']
    return {
        'state': 'telegram-retry-provider-receipt-verified',
        'receipt': receipt,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-retry-delivery-state-commit',
    }


@router.get('/calls')
def list_retry_provider_calls() -> dict:
    return {'count': len(_retry_call_store), 'items': list(_retry_call_store.values()), 'external_calls_made': 0}


@router.get('/receipts')
def list_retry_provider_receipts() -> dict:
    return {'count': len(_retry_receipt_store), 'items': list(_retry_receipt_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_controlled_retry_dispatch_v21_298 import command_center as v21_298_command_center
    html = v21_298_command_center()
    html = html.replace('v21.298', 'v21.299')
    html = html.replace('AURON TELEGRAM CONTROLLED RETRY DISPATCH COMMAND CENTER', 'AURON TELEGRAM RETRY PROVIDER CALL BOUNDARY COMMAND CENTER')
    return html
