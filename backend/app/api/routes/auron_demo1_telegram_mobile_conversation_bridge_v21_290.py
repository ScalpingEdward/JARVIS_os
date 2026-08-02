from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix='/auron/demo1/v21.290', tags=['auron-demo1-telegram-mobile-conversation-bridge'])

_binding_store: dict[str, dict] = {}
_message_store: dict[str, dict] = {}


class TelegramBindRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_user_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    pairing_code_verified: bool = False


class TelegramInboundRequest(BaseModel):
    update_id: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_user_id: str = Field(min_length=1, max_length=120)
    message_id: str = Field(min_length=1, max_length=120)
    text: str | None = Field(default=None, max_length=8000)
    voice_file_id: str | None = Field(default=None, max_length=500)


def reset_telegram_bridge_store() -> None:
    _binding_store.clear()
    _message_store.clear()


@router.get('/status')
def telegram_bridge_status() -> dict:
    return {
        'bindings': len(_binding_store),
        'inbound_messages': len(_message_store),
        'telegram_api_connected': False,
        'webhook_registered': False,
        'voice_transcription_enabled': False,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'bridge_mode': 'contract-and-pairing-foundation',
    }


@router.post('/bind')
def bind_telegram_chat(payload: TelegramBindRequest) -> dict:
    if not payload.pairing_code_verified:
        raise HTTPException(status_code=403, detail='Verified pairing code required')
    existing = _binding_store.get(payload.telegram_chat_id)
    if existing is not None:
        return {'state': 'telegram-chat-already-bound', 'binding': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    record = {
        'binding_id': str(uuid4()),
        'telegram_chat_id': payload.telegram_chat_id,
        'telegram_user_id': payload.telegram_user_id,
        'operator_id': payload.operator_id,
        'workspace_id': payload.workspace_id,
        'bound_by': payload.actor,
        'bound_at': datetime.now(timezone.utc).isoformat(),
        'active': True,
    }
    _binding_store[payload.telegram_chat_id] = record
    return {
        'state': 'telegram-chat-bound',
        'binding': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-webhook-adapter',
        'reply': 'Telegram-Chat ist sicher mit dem AURON-Operatorprofil gekoppelt. Noch wurde keine Telegram-API aufgerufen.',
    }


@router.post('/ingest')
def ingest_telegram_message(payload: TelegramInboundRequest) -> dict:
    binding = _binding_store.get(payload.telegram_chat_id)
    if binding is None or not binding['active']:
        raise HTTPException(status_code=403, detail='Telegram chat is not paired')
    if binding['telegram_user_id'] != payload.telegram_user_id:
        raise HTTPException(status_code=403, detail='Telegram user does not match binding')
    existing = _message_store.get(payload.update_id)
    if existing is not None:
        return {'state': 'telegram-update-already-ingested', 'message': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if not payload.text and not payload.voice_file_id:
        raise HTTPException(status_code=422, detail='Text or voice message required')
    media_type = 'voice' if payload.voice_file_id else 'text'
    record = {
        'update_id': payload.update_id,
        'message_id': payload.message_id,
        'telegram_chat_id': payload.telegram_chat_id,
        'operator_id': binding['operator_id'],
        'workspace_id': binding['workspace_id'],
        'media_type': media_type,
        'text': payload.text,
        'voice_file_id': payload.voice_file_id,
        'received_at': datetime.now(timezone.utc).isoformat(),
        'conversation_routed': False,
        'voice_transcribed': False,
        'reply_sent': False,
    }
    _message_store[payload.update_id] = record
    return {
        'state': 'telegram-message-ingested',
        'message': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-conversation-router' if media_type == 'text' else 'telegram-voice-download-and-transcription',
    }


@router.get('/bindings')
def list_bindings() -> dict:
    return {'count': len(_binding_store), 'items': list(_binding_store.values()), 'external_calls_made': 0}


@router.get('/messages')
def list_messages() -> dict:
    return {'count': len(_message_store), 'items': list(_message_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_alert_lifecycle_closure_v21_289 import command_center as v21_289_command_center
    html = v21_289_command_center()
    html = html.replace('v21.289', 'v21.290')
    html = html.replace('AURON ALERT LIFECYCLE CLOSURE COMMAND CENTER', 'AURON TELEGRAM MOBILE CONVERSATION BRIDGE COMMAND CENTER')
    return html
