from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_live_retry_controller_v21_306 import _live_retry_store
from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import _activation_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider, _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.307', tags=['auron-demo1-telegram-live-controlled-retry-dispatch'])

_live_retry_dispatch_store: dict[str, dict] = {}
_RETRY_EXECUTION_PHRASE = 'EXECUTE ONE AURON TELEGRAM RETRY'


class TelegramLiveRetryDispatchRequest(BaseModel):
    live_retry_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    execution_phrase: str = Field(min_length=1, max_length=160)
    credentials_loaded_in_runtime: bool = False
    network_egress_available: bool = False
    now_iso: str | None = Field(default=None, max_length=80)


def reset_telegram_live_controlled_retry_dispatch_store() -> None:
    _live_retry_dispatch_store.clear()


def _retry_by_id(live_retry_id: str) -> dict | None:
    return next((item for item in _live_retry_store.values() if item['live_retry_id'] == live_retry_id), None)


def _active_authorization() -> dict | None:
    return next((item for item in _activation_store.values() if item.get('active') and item.get('production_transport_authorized')), None)


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@router.get('/status')
def telegram_live_retry_dispatch_status() -> dict:
    return {
        'prepared_live_retry_dispatches': len(_live_retry_dispatch_store),
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'dispatch_mode': 'single-retry-provider-execution-contract',
    }


@router.post('/dispatch')
def dispatch_live_retry(payload: TelegramLiveRetryDispatchRequest) -> dict:
    if payload.execution_phrase != _RETRY_EXECUTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit single-retry execution approval required')

    retry = _retry_by_id(payload.live_retry_id)
    if retry is None:
        raise HTTPException(status_code=404, detail='Telegram live retry not found')

    existing = _live_retry_dispatch_store.get(payload.live_retry_id)
    if existing is not None:
        return {
            'state': 'telegram-live-retry-dispatch-already-prepared',
            'dispatch': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    if retry.get('retry_state') != 'scheduled' or retry.get('terminal') is True:
        raise HTTPException(status_code=409, detail='Scheduled non-terminal Telegram live retry required')

    now = _parse_now(payload.now_iso)
    eligible_at = datetime.fromisoformat(retry['eligible_at'].replace('Z', '+00:00'))
    authorization = _active_authorization()
    provider = _active_provider()
    outbound = _outbound_store.get(retry['correlation_id'])
    checks = {
        'retry_eligible': now >= eligible_at,
        'attempt_within_budget': retry['attempt'] <= retry['max_attempts'],
        'production_authorized': authorization is not None,
        'provider_ready': bool(provider and provider.get('provider_ready')),
        'provider_matches_retry': bool(provider and provider.get('provider_id') == retry.get('provider_id')),
        'provider_matches_authorization': bool(provider and authorization and provider.get('provider_id') == authorization.get('provider_id')),
        'outbound_present': outbound is not None,
        'outbound_matches_retry': bool(outbound and outbound.get('outbound_id') == retry.get('outbound_id')),
        'credentials_loaded_in_runtime': payload.credentials_loaded_in_runtime,
        'network_egress_available': payload.network_egress_available,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'telegram-live-retry-dispatch-blocked',
            'live_retry_id': payload.live_retry_id,
            'checks': checks,
            'blockers': blockers,
            'telegram_api_calls_made': 0,
            'outbound_messages_sent': 0,
            'external_calls_made': 0,
            'next_layer': 'telegram-live-retry-readiness-remediation',
        }

    dispatch_id = str(uuid4())
    record = {
        'live_retry_dispatch_id': dispatch_id,
        'live_retry_id': retry['live_retry_id'],
        'live_delivery_commit_id': retry['live_delivery_commit_id'],
        'previous_execution_id': retry['execution_id'],
        'correlation_id': retry['correlation_id'],
        'activation_id': authorization['activation_id'],
        'provider_id': provider['provider_id'],
        'runtime_id': provider['runtime_id'],
        'outbound_id': outbound['outbound_id'],
        'attempt': retry['attempt'],
        'max_attempts': retry['max_attempts'],
        'method': 'sendMessage',
        'request_body': {
            'chat_id': outbound['telegram_chat_id'],
            'text': outbound['text'],
            'reply_to_message_id': outbound.get('reply_to_message_id'),
            'parse_mode': outbound.get('parse_mode'),
            'disable_notification': outbound.get('disable_notification', False),
        },
        'dispatch_state': 'authorized-awaiting-runtime-worker',
        'provider_call_performed': False,
        'message_sent': False,
        'prepared_by': payload.actor,
        'prepared_at': now.isoformat(),
        'checks': checks,
    }
    _live_retry_dispatch_store[payload.live_retry_id] = record
    retry['retry_state'] = 'dispatch-prepared'
    retry['live_retry_dispatch_id'] = dispatch_id
    outbound['delivery_state'] = 'retry-dispatch-prepared'
    outbound['live_retry_dispatch_id'] = dispatch_id

    return {
        'state': 'telegram-live-retry-dispatch-prepared',
        'dispatch': record,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-live-retry-runtime-worker-provider-call',
    }


@router.get('/dispatches')
def list_live_retry_dispatches() -> dict:
    items = sorted(_live_retry_dispatch_store.values(), key=lambda item: item['prepared_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_live_retry_controller_v21_306 import command_center as v21_306_command_center

    html = v21_306_command_center()
    html = html.replace('v21.306', 'v21.307')
    html = html.replace(
        'AURON TELEGRAM LIVE RETRY CONTROLLER COMMAND CENTER',
        'AURON TELEGRAM LIVE CONTROLLED RETRY DISPATCH COMMAND CENTER',
    )
    return html
