from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_gateway_runtime_v21_291 import _active_runtime
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _binding_store

router = APIRouter(prefix='/auron/demo1/v21.292', tags=['auron-demo1-telegram-provider-registration'])

_provider_store: dict[str, dict] = {}
_outbound_store: dict[str, dict] = {}


class TelegramProviderRegisterRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    provider_name: str = Field(default='telegram-bot-api', min_length=1, max_length=120)
    api_base_url: str = Field(default='https://api.telegram.org', min_length=8, max_length=500)
    webhook_registration_confirmed: bool = False
    provider_identity_verified: bool = False
    dry_run: bool = True


class TelegramOutboundPrepareRequest(BaseModel):
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    correlation_id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=4096)
    reply_to_message_id: str | None = Field(default=None, max_length=120)
    parse_mode: str | None = Field(default=None, pattern='^(MarkdownV2|HTML)$')
    disable_notification: bool = False
    dry_run: bool = True


def reset_telegram_provider_registration_store() -> None:
    _provider_store.clear()
    _outbound_store.clear()


def _active_provider() -> dict | None:
    return next((item for item in _provider_store.values() if item['active']), None)


@router.get('/status')
def telegram_provider_status() -> dict:
    provider = _active_provider()
    return {
        'provider_registered': provider is not None,
        'provider_id': provider['provider_id'] if provider else None,
        'provider_ready': bool(provider and provider['provider_ready']),
        'prepared_outbound_messages': len(_outbound_store),
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'transport_mode': 'controlled-dry-run-contract',
    }


@router.post('/register')
def register_telegram_provider(payload: TelegramProviderRegisterRequest) -> dict:
    runtime = _active_runtime()
    if runtime is None or not runtime['enabled']:
        raise HTTPException(status_code=409, detail='Enabled Telegram gateway runtime required')
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram provider registration is not enabled in v21.292')

    existing = _active_provider()
    if existing is not None:
        same = (
            existing['runtime_id'] == runtime['runtime_id']
            and existing['provider_name'] == payload.provider_name
            and existing['api_base_url'] == payload.api_base_url.rstrip('/')
            and existing['webhook_registration_confirmed'] == payload.webhook_registration_confirmed
            and existing['provider_identity_verified'] == payload.provider_identity_verified
        )
        if same:
            return {
                'state': 'telegram-provider-already-registered',
                'provider': existing,
                'idempotent_replay': True,
                'external_calls_made': 0,
            }
        existing['active'] = False

    provider_id = str(uuid4())
    provider_ready = payload.webhook_registration_confirmed and payload.provider_identity_verified
    record = {
        'provider_id': provider_id,
        'runtime_id': runtime['runtime_id'],
        'provider_name': payload.provider_name,
        'api_base_url': payload.api_base_url.rstrip('/'),
        'webhook_registration_confirmed': payload.webhook_registration_confirmed,
        'provider_identity_verified': payload.provider_identity_verified,
        'provider_ready': provider_ready,
        'active': True,
        'registered_by': payload.actor,
        'registered_at': datetime.now(timezone.utc).isoformat(),
        'registration_mode': 'dry-run-contract',
    }
    _provider_store[provider_id] = record
    return {
        'state': 'telegram-provider-registered',
        'provider': record,
        'provider_api_calls_made': 0,
        'webhook_registration_performed': False,
        'external_calls_made': 0,
        'next_layer': 'telegram-provider-readiness-remediation' if not provider_ready else 'telegram-text-conversation-routing',
        'reply': 'Telegram Provider ist intern registriert. Es wurde noch keine Telegram API aufgerufen.',
    }


@router.post('/prepare-outbound')
def prepare_telegram_outbound(payload: TelegramOutboundPrepareRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram message delivery is not enabled in v21.292')
    provider = _active_provider()
    if provider is None or not provider['provider_ready']:
        raise HTTPException(status_code=409, detail='Ready Telegram provider required')
    binding = _binding_store.get(payload.telegram_chat_id)
    if binding is None or not binding['active']:
        raise HTTPException(status_code=403, detail='Telegram chat is not paired')

    existing = _outbound_store.get(payload.correlation_id)
    if existing is not None:
        return {
            'state': 'telegram-outbound-already-prepared',
            'outbound': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    outbound_id = str(uuid4())
    record = {
        'outbound_id': outbound_id,
        'correlation_id': payload.correlation_id,
        'provider_id': provider['provider_id'],
        'runtime_id': provider['runtime_id'],
        'telegram_chat_id': payload.telegram_chat_id,
        'operator_id': binding['operator_id'],
        'workspace_id': binding['workspace_id'],
        'text': payload.text,
        'reply_to_message_id': payload.reply_to_message_id,
        'parse_mode': payload.parse_mode,
        'disable_notification': payload.disable_notification,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'delivery_state': 'prepared-not-sent',
        'provider_call_performed': False,
        'message_sent': False,
    }
    _outbound_store[payload.correlation_id] = record
    return {
        'state': 'telegram-outbound-prepared',
        'outbound': record,
        'provider_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-text-conversation-routing',
        'reply': 'Telegram-Antwort ist sicher vorbereitet. Noch wurde keine Nachricht versendet.',
    }


@router.get('/outbound')
def list_prepared_outbound() -> dict:
    items = sorted(_outbound_store.values(), key=lambda item: item['prepared_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_gateway_runtime_v21_291 import command_center as v21_291_command_center

    html = v21_291_command_center()
    html = html.replace('v21.291', 'v21.292')
    html = html.replace(
        'AURON TELEGRAM GATEWAY RUNTIME COMMAND CENTER',
        'AURON TELEGRAM PROVIDER REGISTRATION COMMAND CENTER',
    )
    return html
