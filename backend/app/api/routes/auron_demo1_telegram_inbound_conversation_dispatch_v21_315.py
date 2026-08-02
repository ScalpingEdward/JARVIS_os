from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_inbound_webhook_receiver_v21_314 import _webhook_receipt_store
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _message_store
from app.api.routes.auron_demo1_telegram_conversation_router_v21_293 import (
    TelegramConversationRouteRequest,
    route_telegram_conversation,
)

router = APIRouter(prefix='/auron/demo1/v21.315', tags=['auron-demo1-telegram-inbound-conversation-dispatch'])

_dispatch_store: dict[str, dict] = {}


class TelegramInboundConversationDispatchRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    response_text: str | None = Field(default=None, max_length=4096)
    dry_run: bool = True


def reset_telegram_inbound_conversation_dispatch_store() -> None:
    _dispatch_store.clear()


def _verified_receipt(update_id: str) -> dict | None:
    receipt = _webhook_receipt_store.get(update_id)
    if receipt is None or not receipt.get('secret_verified'):
        return None
    return receipt


@router.post('/dispatch')
def dispatch_inbound_conversation(payload: TelegramInboundConversationDispatchRequest) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=409, detail='Live automatic conversation execution is not enabled in v21.315')

    existing = _dispatch_store.get(payload.update_id)
    if existing is not None:
        return {
            'state': 'telegram-inbound-conversation-already-dispatched',
            'dispatch': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    receipt = _verified_receipt(payload.update_id)
    if receipt is None:
        raise HTTPException(status_code=409, detail='Verified Telegram webhook receipt required')

    message = _message_store.get(payload.update_id)
    if message is None:
        raise HTTPException(status_code=404, detail='Ingested Telegram message not found')
    if message.get('media_type') != 'text' or not message.get('text'):
        raise HTTPException(status_code=409, detail='Text Telegram message required for conversation dispatch')

    routed = route_telegram_conversation(TelegramConversationRouteRequest(
        actor=payload.actor,
        update_id=payload.update_id,
        response_text=payload.response_text,
        dry_run=True,
    ))
    conversation = routed['conversation']
    outbound = routed.get('outbound')
    record = {
        'dispatch_id': str(uuid4()),
        'update_id': payload.update_id,
        'webhook_receipt_id': receipt['webhook_receipt_id'],
        'conversation_id': conversation['conversation_id'],
        'correlation_id': conversation['correlation_id'],
        'outbound_id': conversation['outbound_id'],
        'telegram_chat_id': conversation['telegram_chat_id'],
        'operator_id': conversation['operator_id'],
        'workspace_id': conversation['workspace_id'],
        'intent': conversation['intent'],
        'response_text': conversation['response_text'],
        'dispatch_state': 'response-correlated-awaiting-controlled-delivery',
        'model_invoked': conversation['model_invoked'],
        'reply_prepared': conversation['reply_prepared'],
        'reply_sent': False,
        'dispatched_by': payload.actor,
        'dispatched_at': datetime.now(timezone.utc).isoformat(),
    }
    _dispatch_store[payload.update_id] = record
    message['dispatch_id'] = record['dispatch_id']
    message['correlation_id'] = record['correlation_id']

    return {
        'state': 'telegram-inbound-conversation-dispatched',
        'dispatch': record,
        'conversation': conversation,
        'outbound': outbound,
        'model_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-correlated-response-delivery-admission',
    }


@router.get('/status')
def inbound_conversation_dispatch_status() -> dict:
    return {
        'dispatched_updates': len(_dispatch_store),
        'responses_correlated': sum(1 for item in _dispatch_store.values() if item.get('correlation_id')),
        'awaiting_delivery': sum(1 for item in _dispatch_store.values() if not item.get('reply_sent')),
        'model_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'dispatch_mode': 'verified-inbound-to-correlated-response-contract',
    }


@router.get('/dispatches')
def list_inbound_conversation_dispatches() -> dict:
    items = sorted(_dispatch_store.values(), key=lambda item: item['dispatched_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_inbound_webhook_receiver_v21_314 import command_center as v21_314_command_center

    html = v21_314_command_center().replace('v21.314', 'v21.315')
    return html.replace(
        'AURON TELEGRAM INBOUND WEBHOOK RECEIVER COMMAND CENTER',
        'AURON TELEGRAM INBOUND CONVERSATION DISPATCH COMMAND CENTER',
    )
