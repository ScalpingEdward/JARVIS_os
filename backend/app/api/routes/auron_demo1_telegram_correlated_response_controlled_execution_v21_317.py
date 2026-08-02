from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_correlated_response_delivery_admission_v21_316 import _admission_store
from app.api.routes.auron_demo1_telegram_controlled_live_transport_adapter_v21_304 import _live_execution_store
from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import _dispatch_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.317', tags=['auron-demo1-telegram-correlated-response-controlled-execution'])

_execution_handoff_store: dict[str, dict] = {}
_EXECUTION_PHRASE = 'PREPARE ONE AURON TELEGRAM CORRELATED RESPONSE EXECUTION'


class TelegramCorrelatedResponseExecutionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    execution_phrase: str = Field(min_length=1, max_length=200)
    credentials_loaded_in_runtime: bool = False
    network_egress_available: bool = False
    execute_provider_call: bool = False


def reset_telegram_correlated_response_controlled_execution_store() -> None:
    _execution_handoff_store.clear()


@router.post('/prepare-execution')
def prepare_correlated_response_execution(payload: TelegramCorrelatedResponseExecutionRequest) -> dict:
    if payload.execute_provider_call:
        raise HTTPException(status_code=409, detail='v21.317 prepares the runtime-worker contract only; it does not call Telegram')
    if payload.execution_phrase != _EXECUTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit correlated-response execution approval required')

    existing = _execution_handoff_store.get(payload.update_id)
    if existing is not None:
        return {'state': 'telegram-correlated-response-execution-already-prepared', 'handoff': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    admission = _admission_store.get(payload.update_id)
    if admission is None:
        raise HTTPException(status_code=404, detail='Correlated Telegram response admission not found')
    if admission.get('admission_state') != 'authorized-awaiting-controlled-execution-handoff':
        raise HTTPException(status_code=409, detail='Telegram response admission is not awaiting execution handoff')

    dispatch = _dispatch_store.get(payload.update_id)
    outbound = _outbound_store.get(admission['correlation_id'])
    checks = {
        'dispatch_present': dispatch is not None,
        'outbound_present': outbound is not None,
        'dispatch_admission_matches': bool(dispatch and dispatch.get('admission_id') == admission.get('admission_id')),
        'dispatch_state_valid': bool(dispatch and dispatch.get('dispatch_state') == 'delivery-admitted-awaiting-controlled-execution-handoff'),
        'outbound_admission_matches': bool(outbound and outbound.get('admission_id') == admission.get('admission_id')),
        'outbound_state_valid': bool(outbound and outbound.get('delivery_state') == 'delivery-admitted-not-sent' and not outbound.get('message_sent')),
        'outbound_id_matches': bool(outbound and outbound.get('outbound_id') == admission.get('outbound_id')),
        'provider_matches': bool(outbound and outbound.get('provider_id') == admission.get('provider_id')),
        'runtime_matches': bool(outbound and outbound.get('runtime_id') == admission.get('runtime_id')),
        'chat_matches': bool(outbound and str(outbound.get('telegram_chat_id')) == str(admission.get('telegram_chat_id'))),
        'response_text_matches': bool(outbound and outbound.get('text') == admission.get('response_text')),
        'credentials_loaded_in_runtime': payload.credentials_loaded_in_runtime,
        'network_egress_available': payload.network_egress_available,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {'state': 'telegram-correlated-response-execution-blocked', 'update_id': payload.update_id, 'checks': checks, 'blockers': blockers, 'external_calls_made': 0}

    execution_id = str(uuid4())
    execution = {
        'execution_id': execution_id,
        'correlation_id': admission['correlation_id'],
        'activation_id': admission['activation_id'],
        'provider_id': admission['provider_id'],
        'runtime_id': admission['runtime_id'],
        'outbound_id': admission['outbound_id'],
        'dispatch_id': admission['dispatch_id'],
        'admission_id': admission['admission_id'],
        'update_id': payload.update_id,
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
    _live_execution_store[admission['correlation_id']] = execution

    handoff = {
        'handoff_id': str(uuid4()),
        'execution_id': execution_id,
        'update_id': payload.update_id,
        'admission_id': admission['admission_id'],
        'dispatch_id': admission['dispatch_id'],
        'correlation_id': admission['correlation_id'],
        'outbound_id': admission['outbound_id'],
        'handoff_state': 'runtime-worker-ready',
        'prepared_by': payload.actor,
        'prepared_at': execution['prepared_at'],
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
    }
    _execution_handoff_store[payload.update_id] = handoff
    admission['admission_state'] = 'execution-contract-prepared-awaiting-runtime-worker'
    admission['execution_id'] = execution_id
    dispatch['dispatch_state'] = 'execution-contract-prepared-awaiting-runtime-worker'
    dispatch['live_execution_id'] = execution_id
    outbound['delivery_state'] = 'execution-contract-prepared-not-sent'
    outbound['live_execution_id'] = execution_id

    return {
        'state': 'telegram-correlated-response-execution-contract-prepared',
        'handoff': handoff,
        'execution': execution,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-runtime-worker-provider-call',
    }


@router.get('/status')
def controlled_execution_status() -> dict:
    return {
        'execution_handoffs': len(_execution_handoff_store),
        'runtime_worker_ready': sum(1 for item in _execution_handoff_store.values() if item['handoff_state'] == 'runtime-worker-ready'),
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'execution_mode': 'single-correlated-response-runtime-worker-handoff',
    }


@router.get('/handoffs')
def list_execution_handoffs() -> dict:
    items = sorted(_execution_handoff_store.values(), key=lambda item: item['prepared_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_correlated_response_delivery_admission_v21_316 import command_center as v21_316_command_center
    html = v21_316_command_center().replace('v21.316', 'v21.317')
    return html.replace('AURON TELEGRAM CORRELATED RESPONSE DELIVERY ADMISSION COMMAND CENTER', 'AURON TELEGRAM CORRELATED RESPONSE CONTROLLED EXECUTION COMMAND CENTER')
