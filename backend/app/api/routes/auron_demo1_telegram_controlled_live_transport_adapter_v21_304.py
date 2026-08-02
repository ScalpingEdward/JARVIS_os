from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_send_adapter_v21_294 import _send_dispatch_store
from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import _activation_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider, _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.304', tags=['auron-demo1-telegram-controlled-live-transport-adapter'])

_live_execution_store: dict[str, dict] = {}
_live_receipt_store: dict[str, dict] = {}
_EXECUTION_PHRASE = 'EXECUTE ONE AURON TELEGRAM MESSAGE'


class TelegramLiveExecutionRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    execution_phrase: str = Field(min_length=1, max_length=160)
    credentials_loaded_in_runtime: bool = False
    network_egress_available: bool = False
    execute_provider_call: bool = False


class TelegramLiveReceiptRequest(BaseModel):
    execution_id: str = Field(min_length=1, max_length=160)
    accepted: bool
    provider_message_id: str | None = Field(default=None, max_length=160)
    provider_error: str | None = Field(default=None, max_length=500)
    http_status: int = Field(ge=100, le=599)


def reset_telegram_controlled_live_transport_adapter_store() -> None:
    _live_execution_store.clear()
    _live_receipt_store.clear()


def _active_authorization() -> dict | None:
    return next((item for item in _activation_store.values() if item.get('active') and item.get('production_transport_authorized')), None)


def _dispatch_for_correlation(correlation_id: str) -> dict | None:
    return next((item for item in _send_dispatch_store.values() if item.get('correlation_id') == correlation_id), None)


@router.get('/status')
def telegram_live_transport_status() -> dict:
    return {
        'prepared_live_executions': len(_live_execution_store),
        'captured_provider_receipts': len(_live_receipt_store),
        'production_authorization_present': _active_authorization() is not None,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'adapter_mode': 'single-message-live-execution-boundary',
    }


@router.post('/prepare-execution')
def prepare_live_execution(payload: TelegramLiveExecutionRequest) -> dict:
    if payload.execute_provider_call:
        raise HTTPException(status_code=409, detail='Direct Telegram network execution is not performed inside v21.304; use the generated execution contract in the runtime worker')
    if payload.execution_phrase != _EXECUTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit single-message execution approval required')

    existing = _live_execution_store.get(payload.correlation_id)
    if existing is not None:
        return {'state': 'telegram-live-execution-already-prepared', 'execution': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    authorization = _active_authorization()
    provider = _active_provider()
    outbound = _outbound_store.get(payload.correlation_id)
    dispatch = _dispatch_for_correlation(payload.correlation_id)
    checks = {
        'production_authorized': authorization is not None,
        'provider_ready': bool(provider and provider.get('provider_ready')),
        'provider_matches_authorization': bool(provider and authorization and provider.get('provider_id') == authorization.get('provider_id')),
        'outbound_present': outbound is not None,
        'dispatch_present': dispatch is not None,
        'dispatch_prepared': bool(dispatch and dispatch.get('dispatch_state') == 'prepared-not-called'),
        'credentials_loaded_in_runtime': payload.credentials_loaded_in_runtime,
        'network_egress_available': payload.network_egress_available,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {'state': 'telegram-live-execution-blocked', 'correlation_id': payload.correlation_id, 'checks': checks, 'blockers': blockers, 'external_calls_made': 0}

    execution_id = str(uuid4())
    record = {
        'execution_id': execution_id,
        'correlation_id': payload.correlation_id,
        'activation_id': authorization['activation_id'],
        'provider_id': provider['provider_id'],
        'runtime_id': provider['runtime_id'],
        'outbound_id': outbound['outbound_id'],
        'dispatch_id': dispatch['send_dispatch_id'],
        'method': 'sendMessage',
        'request_body': {
            'chat_id': outbound['telegram_chat_id'],
            'text': outbound['text'],
            'reply_to_message_id': outbound.get('reply_to_message_id'),
            'parse_mode': outbound.get('parse_mode'),
            'disable_notification': outbound.get('disable_notification', False),
        },
        'execution_state': 'authorized-awaiting-runtime-worker',
        'provider_call_performed': False,
        'message_sent': False,
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'checks': checks,
    }
    _live_execution_store[payload.correlation_id] = record
    dispatch['dispatch_state'] = 'live-execution-authorized'
    dispatch['live_execution_id'] = execution_id
    outbound['delivery_state'] = 'live-execution-authorized'
    outbound['live_execution_id'] = execution_id
    return {
        'state': 'telegram-live-execution-contract-prepared',
        'execution': record,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-runtime-worker-provider-call',
    }


@router.post('/capture-receipt')
def capture_live_provider_receipt(payload: TelegramLiveReceiptRequest) -> dict:
    execution = next((item for item in _live_execution_store.values() if item['execution_id'] == payload.execution_id), None)
    if execution is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram live execution not found')
    existing = _live_receipt_store.get(payload.execution_id)
    if existing is not None:
        return {'state': 'telegram-live-provider-receipt-already-captured', 'receipt': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if payload.accepted and not payload.provider_message_id:
        raise HTTPException(status_code=422, detail='Accepted Telegram receipt requires provider_message_id')
    if not payload.accepted and not payload.provider_error:
        raise HTTPException(status_code=422, detail='Rejected Telegram receipt requires provider_error')

    receipt = {
        'receipt_id': str(uuid4()),
        'execution_id': payload.execution_id,
        'correlation_id': execution['correlation_id'],
        'accepted': payload.accepted,
        'provider_message_id': payload.provider_message_id,
        'provider_error': payload.provider_error,
        'http_status': payload.http_status,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'verification_state': 'accepted-awaiting-delivery-commit' if payload.accepted else 'rejected-awaiting-delivery-classification',
    }
    _live_receipt_store[payload.execution_id] = receipt
    execution['execution_state'] = 'provider-receipt-captured'
    execution['provider_call_performed'] = True
    execution['message_sent'] = payload.accepted
    return {'state': 'telegram-live-provider-receipt-captured', 'receipt': receipt, 'external_calls_made': 0, 'next_layer': 'telegram-live-delivery-state-commit'}


@router.get('/executions')
def list_live_executions() -> dict:
    return {'count': len(_live_execution_store), 'items': list(_live_execution_store.values()), 'external_calls_made': 0}


@router.get('/receipts')
def list_live_receipts() -> dict:
    return {'count': len(_live_receipt_store), 'items': list(_live_receipt_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import command_center as v21_303_command_center
    html = v21_303_command_center()
    html = html.replace('v21.303', 'v21.304')
    html = html.replace('AURON TELEGRAM PRODUCTION ACTIVATION GATE COMMAND CENTER', 'AURON TELEGRAM CONTROLLED LIVE TRANSPORT ADAPTER COMMAND CENTER')
    return html
