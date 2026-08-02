from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import (
    TelegramInboundRequest,
    _binding_store,
    ingest_telegram_message,
)

router = APIRouter(prefix='/auron/demo1/v21.291', tags=['auron-demo1-telegram-gateway-runtime'])

_runtime_store: dict[str, dict] = {}
_webhook_update_store: dict[str, dict] = {}


class TelegramRuntimeConfigureRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    bot_token: str = Field(min_length=20, max_length=500)
    webhook_base_url: str = Field(min_length=8, max_length=500)
    webhook_secret: str = Field(min_length=16, max_length=500)
    mode: str = Field(default='webhook', pattern='^(webhook|polling)$')
    enabled: bool = False


class TelegramWebhookUpdateRequest(BaseModel):
    secret_token: str = Field(min_length=1, max_length=500)
    update_id: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    telegram_user_id: str = Field(min_length=1, max_length=120)
    message_id: str = Field(min_length=1, max_length=120)
    text: str | None = Field(default=None, max_length=8000)
    voice_file_id: str | None = Field(default=None, max_length=500)


def reset_telegram_gateway_runtime_store() -> None:
    _runtime_store.clear()
    _webhook_update_store.clear()


def _digest(value: str) -> str:
    return sha256(value.encode('utf-8')).hexdigest()


def _active_runtime() -> dict | None:
    return next((item for item in _runtime_store.values() if item['active']), None)


@router.get('/status')
def telegram_gateway_status() -> dict:
    runtime = _active_runtime()
    return {
        'configured': runtime is not None,
        'runtime_id': runtime['runtime_id'] if runtime else None,
        'mode': runtime['mode'] if runtime else None,
        'enabled': bool(runtime and runtime['enabled']),
        'webhook_ready': bool(runtime and runtime['mode'] == 'webhook' and runtime['enabled']),
        'processed_updates': len(_webhook_update_store),
        'paired_chats': len(_binding_store),
        'telegram_api_calls_made': 0,
        'webhook_registration_performed': False,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'runtime_mode': 'secure-local-gateway-contract',
    }


@router.post('/configure')
def configure_telegram_runtime(payload: TelegramRuntimeConfigureRequest) -> dict:
    existing = _active_runtime()
    token_digest = _digest(payload.bot_token)
    secret_digest = _digest(payload.webhook_secret)
    if existing is not None:
        same = (
            existing['bot_token_digest'] == token_digest
            and existing['webhook_secret_digest'] == secret_digest
            and existing['webhook_base_url'] == payload.webhook_base_url.rstrip('/')
            and existing['mode'] == payload.mode
            and existing['enabled'] == payload.enabled
        )
        if same:
            return {
                'state': 'telegram-runtime-already-configured',
                'runtime': existing,
                'idempotent_replay': True,
                'external_calls_made': 0,
            }
        existing['active'] = False

    runtime_id = str(uuid4())
    configured_at = datetime.now(timezone.utc).isoformat()
    record = {
        'runtime_id': runtime_id,
        'mode': payload.mode,
        'enabled': payload.enabled,
        'active': True,
        'webhook_base_url': payload.webhook_base_url.rstrip('/'),
        'webhook_path': f'/auron/demo1/v21.291/webhook/{runtime_id}',
        'bot_token_digest': token_digest,
        'webhook_secret_digest': secret_digest,
        'credentials_stored_in_plaintext': False,
        'configured_by': payload.actor,
        'configured_at': configured_at,
        'last_heartbeat_at': None,
        'connection_state': 'configured-disabled' if not payload.enabled else 'ready-for-provider-registration',
    }
    _runtime_store[runtime_id] = record
    return {
        'state': 'telegram-runtime-configured',
        'runtime': record,
        'telegram_api_calls_made': 0,
        'webhook_registration_performed': False,
        'external_calls_made': 0,
        'next_layer': 'telegram-provider-registration' if payload.enabled else 'telegram-runtime-enable',
        'reply': 'Telegram Gateway Runtime ist sicher konfiguriert. Token und Secret werden nur als Hash gespeichert; die Telegram API wurde noch nicht aufgerufen.',
    }


@router.post('/heartbeat')
def telegram_runtime_heartbeat() -> dict:
    runtime = _active_runtime()
    if runtime is None:
        raise HTTPException(status_code=409, detail='Telegram runtime is not configured')
    now = datetime.now(timezone.utc).isoformat()
    runtime['last_heartbeat_at'] = now
    return {
        'state': 'telegram-runtime-heartbeat-recorded',
        'runtime_id': runtime['runtime_id'],
        'heartbeat_at': now,
        'connection_state': runtime['connection_state'],
        'external_calls_made': 0,
    }


@router.post('/webhook/{runtime_id}')
def receive_telegram_webhook(runtime_id: str, payload: TelegramWebhookUpdateRequest) -> dict:
    runtime = _runtime_store.get(runtime_id)
    if runtime is None or not runtime['active']:
        raise HTTPException(status_code=404, detail='Telegram runtime not found')
    if runtime['mode'] != 'webhook' or not runtime['enabled']:
        raise HTTPException(status_code=409, detail='Telegram webhook runtime is not enabled')
    if runtime['webhook_secret_digest'] != _digest(payload.secret_token):
        raise HTTPException(status_code=403, detail='Invalid Telegram webhook secret')

    existing = _webhook_update_store.get(payload.update_id)
    if existing is not None:
        return {
            'state': 'telegram-webhook-update-already-processed',
            'gateway_record': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    bridge_result = ingest_telegram_message(
        TelegramInboundRequest(
            update_id=payload.update_id,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_user_id=payload.telegram_user_id,
            message_id=payload.message_id,
            text=payload.text,
            voice_file_id=payload.voice_file_id,
        )
    )
    record = {
        'update_id': payload.update_id,
        'runtime_id': runtime_id,
        'message_id': payload.message_id,
        'telegram_chat_id': payload.telegram_chat_id,
        'media_type': bridge_result['message']['media_type'],
        'bridge_state': bridge_result['state'],
        'received_at': datetime.now(timezone.utc).isoformat(),
        'conversation_routed': False,
        'reply_sent': False,
    }
    _webhook_update_store[payload.update_id] = record
    return {
        'state': 'telegram-webhook-update-accepted',
        'gateway_record': record,
        'bridge_result': bridge_result,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-text-conversation-routing' if record['media_type'] == 'text' else 'telegram-voice-media-intake',
    }


@router.get('/updates')
def list_gateway_updates() -> dict:
    items = sorted(_webhook_update_store.values(), key=lambda item: item['received_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import command_center as v21_290_command_center

    html = v21_290_command_center()
    html = html.replace('v21.290', 'v21.291')
    html = html.replace(
        'AURON TELEGRAM MOBILE CONVERSATION BRIDGE COMMAND CENTER',
        'AURON TELEGRAM GATEWAY RUNTIME COMMAND CENTER',
    )
    return html
