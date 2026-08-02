from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_secure_bot_provisioning_v21_312 import _validation_store
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _binding_store

router = APIRouter(prefix='/auron/demo1/v21.313', tags=['auron-demo1-telegram-end-to-end-validation-session'])

_validation_session_store: dict[str, dict] = {}
_START_PHRASE = 'START ONE AURON TELEGRAM END TO END VALIDATION'


class TelegramEndToEndValidationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=160)
    operator_id: str = Field(min_length=1, max_length=160)
    telegram_chat_id: str = Field(min_length=1, max_length=160)
    test_message: str = Field(min_length=1, max_length=1000)
    approval_phrase: str = Field(min_length=1, max_length=160)


class TelegramEndToEndValidationCompleteRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=160)
    inbound_received: bool
    conversation_routed: bool
    outbound_prepared: bool
    provider_call_completed: bool
    phone_reply_observed: bool
    correlation_id: str | None = Field(default=None, max_length=160)
    provider_message_id: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=500)


def reset_telegram_end_to_end_validation_session_store() -> None:
    _validation_session_store.clear()


def _runtime_validation() -> dict | None:
    return next((item for item in _validation_store.values() if item.get('runtime_ready')), None)


def _paired_chat(operator_id: str, chat_id: str) -> dict | None:
    return next(
        (
            item
            for item in _binding_store.values()
            if item.get('operator_id') == operator_id
            and str(item.get('telegram_chat_id')) == str(chat_id)
            and item.get('active') is True
        ),
        None,
    )


@router.get('/status')
def validation_session_status() -> dict:
    return {
        'sessions': len(_validation_session_store),
        'running': sum(1 for item in _validation_session_store.values() if item['state'] == 'awaiting-evidence'),
        'passed': sum(1 for item in _validation_session_store.values() if item['state'] == 'passed'),
        'failed': sum(1 for item in _validation_session_store.values() if item['state'] == 'failed'),
        'external_calls_made': 0,
        'session_mode': 'controlled-end-to-end-evidence-validation',
    }


@router.post('/start')
def start_validation_session(payload: TelegramEndToEndValidationStartRequest) -> dict:
    if payload.approval_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram end-to-end validation approval required')

    validation = _runtime_validation()
    pairing = _paired_chat(payload.operator_id, payload.telegram_chat_id)
    checks = {
        'runtime_provisioning_validated': validation is not None,
        'operator_chat_paired': pairing is not None,
        'test_message_present': bool(payload.test_message.strip()),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'telegram-end-to-end-validation-blocked',
            'checks': checks,
            'blockers': blockers,
            'external_calls_made': 0,
            'next_layer': 'telegram-end-to-end-readiness-remediation',
        }

    session_key = f"{payload.workspace_id}:{payload.operator_id}:{payload.telegram_chat_id}:{payload.test_message}"
    existing = _validation_session_store.get(session_key)
    if existing is not None:
        return {'state': 'telegram-end-to-end-validation-already-started', 'session': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    record = {
        'session_id': str(uuid4()),
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'telegram_chat_id': payload.telegram_chat_id,
        'test_message': payload.test_message,
        'bot_id': validation['bot_id'],
        'token_fingerprint': validation['token_fingerprint'],
        'pairing_id': pairing.get('binding_id'),
        'state': 'awaiting-evidence',
        'checks': checks,
        'started_by': payload.actor,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _validation_session_store[session_key] = record
    return {
        'state': 'telegram-end-to-end-validation-started',
        'session': record,
        'external_calls_made': 0,
        'next_layer': 'execute-controlled-phone-message-and-submit-evidence',
    }


@router.post('/complete')
def complete_validation_session(payload: TelegramEndToEndValidationCompleteRequest) -> dict:
    session = next((item for item in _validation_session_store.values() if item['session_id'] == payload.session_id), None)
    if session is None:
        raise HTTPException(status_code=404, detail='Telegram end-to-end validation session not found')
    if session['state'] in {'passed', 'failed'}:
        return {'state': 'telegram-end-to-end-validation-already-completed', 'session': session, 'idempotent_replay': True, 'external_calls_made': 0}

    evidence = {
        'inbound_received': payload.inbound_received,
        'conversation_routed': payload.conversation_routed,
        'outbound_prepared': payload.outbound_prepared,
        'provider_call_completed': payload.provider_call_completed,
        'phone_reply_observed': payload.phone_reply_observed,
        'correlation_id_present': bool(payload.correlation_id),
        'provider_message_id_present': bool(payload.provider_message_id),
    }
    passed = all(evidence.values())
    session.update({
        'state': 'passed' if passed else 'failed',
        'evidence': evidence,
        'correlation_id': payload.correlation_id,
        'provider_message_id': payload.provider_message_id,
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'note': payload.note,
        'chain_complete': passed,
    })
    return {
        'state': 'telegram-end-to-end-validation-passed' if passed else 'telegram-end-to-end-validation-failed',
        'session': session,
        'external_calls_made': 0,
        'next_layer': 'telegram-inbound-webhook-processing' if passed else 'telegram-end-to-end-evidence-remediation',
    }


@router.get('/sessions')
def list_validation_sessions() -> dict:
    items = sorted(_validation_session_store.values(), key=lambda item: item['started_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_secure_bot_provisioning_v21_312 import command_center as v21_312_command_center
    html = v21_312_command_center().replace('v21.312', 'v21.313')
    return html.replace('AURON TELEGRAM SECURE BOT PROVISIONING COMMAND CENTER', 'AURON TELEGRAM END TO END VALIDATION COMMAND CENTER')
