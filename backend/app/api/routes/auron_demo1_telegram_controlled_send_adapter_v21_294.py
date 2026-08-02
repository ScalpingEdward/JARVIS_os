from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_conversation_router_v21_293 import _conversation_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider, _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.294', tags=['auron-demo1-telegram-controlled-send-adapter'])

_dispatch_store: dict[str, dict] = {}


class TelegramSendDispatchRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    provider_identity_verified: bool = False
    transport_ready: bool = False
    dry_run: bool = True


def reset_telegram_controlled_send_store() -> None:
    _dispatch_store.clear()


@router.get('/status')
def telegram_send_status() -> dict:
    return {
        'prepared_dispatches': len(_dispatch_store),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'adapter_mode': 'controlled-dry-run-dispatch',
    }


@router.post('/dispatch')
def dispatch_telegram_reply(payload: TelegramSendDispatchRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram send is not enabled in v21.294')

    existing = _dispatch_store.get(payload.correlation_id)
    if existing is not None:
        return {
            'state': 'telegram-send-dispatch-already-prepared',
            'dispatch': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    outbound = _outbound_store.get(payload.correlation_id)
    if outbound is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram outbound message not found')
    if outbound.get('delivery_state') != 'prepared-not-sent':
        raise HTTPException(status_code=409, detail='Telegram outbound message is not dispatchable')

    provider = _active_provider()
    if provider is None or not provider.get('provider_ready'):
        raise HTTPException(status_code=409, detail='Ready Telegram provider required')

    conversation = next(
        (item for item in _conversation_store.values() if item['correlation_id'] == payload.correlation_id),
        None,
    )
    if conversation is None:
        raise HTTPException(status_code=409, detail='Correlated Telegram conversation required')

    blockers: list[str] = []
    if not payload.provider_identity_verified:
        blockers.append('provider_identity_verified')
    if not payload.transport_ready:
        blockers.append('transport_ready')
    if provider['provider_id'] != outbound['provider_id']:
        blockers.append('provider_id_mismatch')
    if conversation['outbound_id'] != outbound['outbound_id']:
        blockers.append('outbound_correlation_mismatch')

    if blockers:
        return {
            'state': 'telegram-send-dispatch-blocked',
            'correlation_id': payload.correlation_id,
            'blockers': blockers,
            'provider_api_calls_made': 0,
            'outbound_messages_sent': 0,
            'external_calls_made': 0,
            'next_layer': 'telegram-send-readiness-remediation',
        }

    dispatch_id = str(uuid4())
    record = {
        'dispatch_id': dispatch_id,
        'correlation_id': payload.correlation_id,
        'conversation_id': conversation['conversation_id'],
        'outbound_id': outbound['outbound_id'],
        'provider_id': provider['provider_id'],
        'runtime_id': provider['runtime_id'],
        'telegram_chat_id': outbound['telegram_chat_id'],
        'reply_to_message_id': outbound['reply_to_message_id'],
        'text': outbound['text'],
        'dispatch_state': 'prepared-not-called',
        'provider_call_performed': False,
        'message_sent': False,
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
    }
    _dispatch_store[payload.correlation_id] = record
    outbound['delivery_state'] = 'dispatch-prepared'
    outbound['dispatch_id'] = dispatch_id

    return {
        'state': 'telegram-send-dispatch-prepared',
        'dispatch': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-provider-call-boundary',
        'reply': 'Telegram-Sendeauftrag wurde kontrolliert vorbereitet. Die Telegram API wurde noch nicht aufgerufen.',
    }


@router.get('/dispatches')
def list_telegram_dispatches() -> dict:
    items = sorted(_dispatch_store.values(), key=lambda item: item['prepared_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_conversation_router_v21_293 import command_center as v21_293_command_center

    html = v21_293_command_center()
    html = html.replace('v21.293', 'v21.294')
    html = html.replace(
        'AURON TELEGRAM CONVERSATION ROUTER COMMAND CENTER',
        'AURON TELEGRAM CONTROLLED SEND ADAPTER COMMAND CENTER',
    )
    return html
