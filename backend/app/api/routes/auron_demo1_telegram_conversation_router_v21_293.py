from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _message_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import (
    TelegramOutboundPrepareRequest,
    _active_provider,
    prepare_telegram_outbound,
)

router = APIRouter(prefix='/auron/demo1/v21.293', tags=['auron-demo1-telegram-conversation-router'])

_conversation_store: dict[str, dict] = {}


class TelegramConversationRouteRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    response_text: str | None = Field(default=None, max_length=4096)
    dry_run: bool = True


def reset_telegram_conversation_router_store() -> None:
    _conversation_store.clear()


def _classify_intent(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ('status', 'bereit', 'health')):
        return 'system-status'
    if any(token in lowered for token in ('trade', 'trading', 'mt5', 'markt')):
        return 'trading-assistance'
    if any(token in lowered for token in ('erinner', 'termin', 'kalender')):
        return 'personal-organization'
    return 'general-conversation'


def _fallback_reply(intent: str) -> str:
    replies = {
        'system-status': 'AURON ist online. Die Telegram-Nachricht wurde sicher verarbeitet.',
        'trading-assistance': 'Die Trading-Anfrage wurde erkannt und wartet auf die zuständige, kontrollierte Analyse-Schicht.',
        'personal-organization': 'Die Organisationsanfrage wurde erkannt und wartet auf die zuständige Connector-Schicht.',
        'general-conversation': 'Nachricht verstanden. Die vollständige AURON-Modellantwort wird in der nächsten kontrollierten Schicht verbunden.',
    }
    return replies[intent]


@router.get('/status')
def telegram_conversation_status() -> dict:
    return {
        'routed_conversations': len(_conversation_store),
        'model_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'router_mode': 'governed-internal-conversation-contract',
    }


@router.post('/route')
def route_telegram_conversation(payload: TelegramConversationRouteRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live Telegram conversation delivery is not enabled in v21.293')

    message = _message_store.get(payload.update_id)
    if message is None:
        raise HTTPException(status_code=404, detail='Telegram message not found')
    if message['media_type'] != 'text' or not message.get('text'):
        raise HTTPException(status_code=409, detail='Text Telegram message required')
    provider = _active_provider()
    if provider is None or not provider['provider_ready']:
        raise HTTPException(status_code=409, detail='Ready Telegram provider required')

    existing = _conversation_store.get(payload.update_id)
    if existing is not None:
        return {
            'state': 'telegram-conversation-already-routed',
            'conversation': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    intent = _classify_intent(message['text'])
    correlation_id = f"telegram-{payload.update_id}-{uuid4()}"
    response_text = payload.response_text or _fallback_reply(intent)
    outbound_result = prepare_telegram_outbound(
        TelegramOutboundPrepareRequest(
            telegram_chat_id=message['telegram_chat_id'],
            correlation_id=correlation_id,
            text=response_text,
            reply_to_message_id=message['message_id'],
            dry_run=True,
        )
    )
    routed_at = datetime.now(timezone.utc).isoformat()
    record = {
        'conversation_id': str(uuid4()),
        'correlation_id': correlation_id,
        'update_id': payload.update_id,
        'telegram_chat_id': message['telegram_chat_id'],
        'operator_id': message['operator_id'],
        'workspace_id': message['workspace_id'],
        'source_text': message['text'],
        'intent': intent,
        'dialogue_request_created': True,
        'governance_checked': True,
        'model_invoked': False,
        'response_text': response_text,
        'outbound_id': outbound_result['outbound']['outbound_id'],
        'reply_prepared': True,
        'reply_sent': False,
        'routed_by': payload.actor,
        'routed_at': routed_at,
    }
    _conversation_store[payload.update_id] = record
    message['conversation_routed'] = True
    message['conversation_id'] = record['conversation_id']

    return {
        'state': 'telegram-conversation-routed',
        'conversation': record,
        'outbound': outbound_result['outbound'],
        'model_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-controlled-send-adapter',
        'reply': 'Telegram-Text wurde intern zu AURON geroutet und die Antwort vorbereitet. Noch wurde nichts versendet.',
    }


@router.get('/conversations')
def list_telegram_conversations() -> dict:
    items = sorted(_conversation_store.values(), key=lambda item: item['routed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import command_center as v21_292_command_center

    html = v21_292_command_center()
    html = html.replace('v21.292', 'v21.293')
    html = html.replace(
        'AURON TELEGRAM PROVIDER REGISTRATION COMMAND CENTER',
        'AURON TELEGRAM CONVERSATION ROUTER COMMAND CENTER',
    )
    return html
