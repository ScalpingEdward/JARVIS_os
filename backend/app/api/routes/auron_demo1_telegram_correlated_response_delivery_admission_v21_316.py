from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import _dispatch_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store
from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import _activation_store

router = APIRouter(prefix='/auron/demo1/v21.316', tags=['auron-demo1-telegram-correlated-response-delivery-admission'])

_admission_store: dict[str, dict] = {}
_APPROVAL_PHRASE = 'ADMIT ONE AURON TELEGRAM CORRELATED RESPONSE'


class TelegramCorrelatedResponseAdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    approval_phrase: str = Field(min_length=1, max_length=180)
    dry_run: bool = True


def reset_telegram_correlated_response_delivery_admission_store() -> None:
    _admission_store.clear()


def _active_activation() -> dict | None:
    return next((item for item in _activation_store.values() if item.get('active') and item.get('production_transport_authorized')), None)


@router.post('/admit')
def admit_correlated_response(payload: TelegramCorrelatedResponseAdmissionRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='v21.316 authorizes a handoff only; provider execution is not performed here')
    if payload.approval_phrase != _APPROVAL_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit correlated-response delivery approval required')

    existing = _admission_store.get(payload.update_id)
    if existing is not None:
        return {'state': 'telegram-correlated-response-already-admitted', 'admission': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    dispatch = _dispatch_store.get(payload.update_id)
    if dispatch is None:
        raise HTTPException(status_code=404, detail='Correlated Telegram inbound dispatch not found')
    if dispatch.get('dispatch_state') != 'response-correlated-awaiting-controlled-delivery':
        raise HTTPException(status_code=409, detail='Telegram dispatch is not awaiting controlled delivery')
    if dispatch.get('reply_sent'):
        raise HTTPException(status_code=409, detail='Telegram response was already sent')

    outbound = _outbound_store.get(dispatch['correlation_id'])
    if outbound is None:
        raise HTTPException(status_code=404, detail='Correlated Telegram outbound contract not found')
    checks = {
        'outbound_id_matches': outbound.get('outbound_id') == dispatch.get('outbound_id'),
        'chat_matches': str(outbound.get('telegram_chat_id')) == str(dispatch.get('telegram_chat_id')),
        'operator_matches': outbound.get('operator_id') == dispatch.get('operator_id'),
        'workspace_matches': outbound.get('workspace_id') == dispatch.get('workspace_id'),
        'response_text_matches': outbound.get('text') == dispatch.get('response_text'),
        'outbound_prepared_not_sent': outbound.get('delivery_state') == 'prepared-not-sent' and not outbound.get('message_sent'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Correlated Telegram delivery chain is inconsistent', 'blockers': blockers})

    activation = _active_activation()
    if activation is None:
        raise HTTPException(status_code=409, detail='Active Telegram production transport authorization required')
    if activation.get('provider_id') != outbound.get('provider_id') or activation.get('runtime_id') != outbound.get('runtime_id'):
        raise HTTPException(status_code=409, detail='Telegram activation does not match the correlated outbound provider/runtime')

    record = {
        'admission_id': str(uuid4()),
        'update_id': payload.update_id,
        'dispatch_id': dispatch['dispatch_id'],
        'conversation_id': dispatch['conversation_id'],
        'correlation_id': dispatch['correlation_id'],
        'outbound_id': dispatch['outbound_id'],
        'activation_id': activation['activation_id'],
        'provider_id': outbound['provider_id'],
        'runtime_id': outbound['runtime_id'],
        'telegram_chat_id': outbound['telegram_chat_id'],
        'reply_to_message_id': outbound.get('reply_to_message_id'),
        'response_text': outbound['text'],
        'checks': checks,
        'admission_state': 'authorized-awaiting-controlled-execution-handoff',
        'admitted_by': payload.actor,
        'admitted_at': datetime.now(timezone.utc).isoformat(),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
    }
    _admission_store[payload.update_id] = record
    dispatch['dispatch_state'] = 'delivery-admitted-awaiting-controlled-execution-handoff'
    dispatch['admission_id'] = record['admission_id']
    outbound['delivery_state'] = 'delivery-admitted-not-sent'
    outbound['admission_id'] = record['admission_id']

    return {
        'state': 'telegram-correlated-response-delivery-admitted',
        'admission': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-correlated-response-controlled-execution-contract',
    }


@router.get('/status')
def admission_status() -> dict:
    return {
        'admissions': len(_admission_store),
        'awaiting_execution_handoff': sum(1 for item in _admission_store.values() if item['admission_state'] == 'authorized-awaiting-controlled-execution-handoff'),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'admission_mode': 'operator-approved-correlated-response-handoff',
    }


@router.get('/admissions')
def list_admissions() -> dict:
    items = sorted(_admission_store.values(), key=lambda item: item['admitted_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import command_center as v21_315_command_center
    html = v21_315_command_center().replace('v21.315', 'v21.316')
    return html.replace('AURON TELEGRAM INBOUND CONVERSATION DISPATCH COMMAND CENTER', 'AURON TELEGRAM CORRELATED RESPONSE DELIVERY ADMISSION COMMAND CENTER')
