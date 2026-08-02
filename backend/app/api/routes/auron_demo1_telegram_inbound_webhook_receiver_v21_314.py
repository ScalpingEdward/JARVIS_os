from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import (
    TelegramInboundRequest,
    _binding_store,
    ingest_telegram_message,
)

router = APIRouter(
    prefix='/auron/demo1/v21.314',
    tags=['auron-demo1-telegram-inbound-webhook-receiver'],
)

_webhook_receipt_store: dict[str, dict] = {}


class TelegramWebhookUser(BaseModel):
    id: int | str


class TelegramWebhookChat(BaseModel):
    id: int | str


class TelegramWebhookVoice(BaseModel):
    file_id: str = Field(min_length=1, max_length=500)


class TelegramWebhookMessage(BaseModel):
    message_id: int | str
    from_user: TelegramWebhookUser | None = Field(default=None, alias='from')
    chat: TelegramWebhookChat
    text: str | None = Field(default=None, max_length=8000)
    voice: TelegramWebhookVoice | None = None


class TelegramWebhookUpdate(BaseModel):
    update_id: int | str
    message: TelegramWebhookMessage | None = None


def reset_telegram_inbound_webhook_receiver_store() -> None:
    _webhook_receipt_store.clear()


def _configured_secret() -> str | None:
    value = os.getenv('TELEGRAM_WEBHOOK_SECRET', '').strip()
    return value or None


def _verify_secret(received: str | None) -> None:
    expected = _configured_secret()
    if expected is None:
        raise HTTPException(status_code=503, detail='Telegram webhook secret is not configured')
    if received is None or not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=403, detail='Invalid Telegram webhook secret')


def _active_binding(chat_id: str, user_id: str) -> dict | None:
    binding = _binding_store.get(chat_id)
    if binding is None or not binding.get('active'):
        return None
    if str(binding.get('telegram_user_id')) != user_id:
        return None
    return binding


@router.post('/webhook')
def receive_telegram_webhook(
    payload: TelegramWebhookUpdate,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    _verify_secret(x_telegram_bot_api_secret_token)

    update_id = str(payload.update_id)
    existing = _webhook_receipt_store.get(update_id)
    if existing is not None:
        return {
            'state': 'telegram-webhook-update-already-received',
            'receipt': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    message = payload.message
    if message is None:
        raise HTTPException(status_code=422, detail='Telegram message update required')
    if message.from_user is None:
        raise HTTPException(status_code=422, detail='Telegram sender required')

    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    binding = _active_binding(chat_id, user_id)
    if binding is None:
        raise HTTPException(status_code=403, detail='Telegram sender or chat is not actively paired')

    voice_file_id = message.voice.file_id if message.voice is not None else None
    if not message.text and not voice_file_id:
        raise HTTPException(status_code=422, detail='Telegram text or voice message required')

    ingest_result = ingest_telegram_message(TelegramInboundRequest(
        update_id=update_id,
        telegram_chat_id=chat_id,
        telegram_user_id=user_id,
        message_id=str(message.message_id),
        text=message.text,
        voice_file_id=voice_file_id,
    ))

    receipt = {
        'webhook_receipt_id': str(uuid4()),
        'update_id': update_id,
        'message_id': str(message.message_id),
        'telegram_chat_id': chat_id,
        'telegram_user_id': user_id,
        'operator_id': binding.get('operator_id'),
        'workspace_id': binding.get('workspace_id'),
        'media_type': 'voice' if voice_file_id else 'text',
        'bridge_state': ingest_result['state'],
        'received_at': datetime.now(timezone.utc).isoformat(),
        'secret_verified': True,
        'external_calls_made': 0,
    }
    _webhook_receipt_store[update_id] = receipt
    return {
        'state': 'telegram-webhook-update-accepted',
        'receipt': receipt,
        'message': ingest_result['message'],
        'external_calls_made': 0,
        'next_layer': ingest_result['next_layer'],
    }


@router.get('/status')
def webhook_receiver_status() -> dict:
    return {
        'webhook_secret_configured': _configured_secret() is not None,
        'accepted_updates': len(_webhook_receipt_store),
        'text_updates': sum(1 for item in _webhook_receipt_store.values() if item['media_type'] == 'text'),
        'voice_updates': sum(1 for item in _webhook_receipt_store.values() if item['media_type'] == 'voice'),
        'webhook_mode': 'secret-verified-controlled-ingestion',
        'external_calls_made': 0,
    }


@router.get('/receipts')
def list_webhook_receipts() -> dict:
    items = sorted(_webhook_receipt_store.values(), key=lambda item: item['received_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_end_to_end_validation_session_v21_313 import command_center as v21_313_command_center

    html = v21_313_command_center().replace('v21.313', 'v21.314')
    return html.replace(
        'AURON TELEGRAM END TO END VALIDATION COMMAND CENTER',
        'AURON TELEGRAM INBOUND WEBHOOK RECEIVER COMMAND CENTER',
    )
