from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _binding_store
from app.api.routes.auron_demo1_telegram_phone_validation_reconciliation_v21_321 import _reconciliation_store
from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import _activation_store

router = APIRouter(prefix='/auron/demo1/v21.322', tags=['auron-demo1-telegram-operational-go-live-acceptance'])

_go_live_store: dict[str, dict] = {}
_ACCEPTANCE_PHRASE = 'ACCEPT AURON TELEGRAM OPERATIONAL GO LIVE'
_PAUSE_PHRASE = 'PAUSE AURON TELEGRAM CONTINUOUS MODE'


class TelegramOperationalGoLiveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    validation_run_id: str = Field(min_length=1, max_length=160)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    acceptance_phrase: str = Field(min_length=1, max_length=200)
    max_messages_per_minute: int = Field(default=12, ge=1, le=60)
    max_concurrent_conversations: int = Field(default=1, ge=1, le=10)
    require_operator_binding: bool = True
    enable_continuous_mode: bool = True


class TelegramContinuousModePauseRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    pause_phrase: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)


def reset_telegram_operational_go_live_acceptance_store() -> None:
    _go_live_store.clear()


def _passed_reconciliation(validation_run_id: str) -> dict | None:
    item = _reconciliation_store.get(validation_run_id)
    if item and item.get('validation_passed') and item.get('reconciliation_state') == 'passed':
        return item
    return None


def _active_activation() -> dict | None:
    return next((item for item in _activation_store.values() if item.get('active') and item.get('production_transport_authorized')), None)


@router.post('/accept')
def accept_operational_go_live(payload: TelegramOperationalGoLiveRequest) -> dict:
    if payload.acceptance_phrase != _ACCEPTANCE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram operational go-live acceptance required')
    if not payload.enable_continuous_mode:
        raise HTTPException(status_code=409, detail='Continuous conversation mode must be explicitly enabled for go-live acceptance')

    existing = _go_live_store.get(payload.telegram_chat_id)
    if existing is not None and existing.get('continuous_mode_active'):
        return {
            'state': 'telegram-operational-go-live-already-active',
            'acceptance': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    reconciliation = _passed_reconciliation(payload.validation_run_id)
    if reconciliation is None:
        raise HTTPException(status_code=409, detail='Passed Telegram phone-validation reconciliation required')
    if str(reconciliation.get('telegram_chat_id')) != str(payload.telegram_chat_id):
        raise HTTPException(status_code=409, detail='Phone-validation chat does not match requested go-live chat')

    binding = _binding_store.get(payload.telegram_chat_id)
    activation = _active_activation()
    checks = {
        'phone_validation_passed': True,
        'integrity_hash_present': bool(reconciliation.get('integrity_hash')),
        'immutable_reconciliation': reconciliation.get('immutable') is True,
        'active_production_activation': activation is not None,
        'operator_binding_present': binding is not None if payload.require_operator_binding else True,
        'operator_binding_active': bool(binding and binding.get('active')) if payload.require_operator_binding else True,
        'chat_matches_binding': bool(binding and str(binding.get('telegram_chat_id')) == str(payload.telegram_chat_id)) if payload.require_operator_binding else True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram go-live acceptance blocked', 'blockers': blockers})

    accepted_at = datetime.now(timezone.utc).isoformat()
    record = {
        'go_live_acceptance_id': str(uuid4()),
        'validation_run_id': payload.validation_run_id,
        'reconciliation_id': reconciliation['reconciliation_id'],
        'reconciliation_integrity_hash': reconciliation['integrity_hash'],
        'activation_id': activation['activation_id'],
        'telegram_chat_id': payload.telegram_chat_id,
        'telegram_user_id': binding.get('telegram_user_id') if binding else None,
        'operator_id': binding.get('operator_id') if binding else reconciliation.get('operator_id'),
        'workspace_id': binding.get('workspace_id') if binding else reconciliation.get('workspace_id'),
        'checks': checks,
        'max_messages_per_minute': payload.max_messages_per_minute,
        'max_concurrent_conversations': payload.max_concurrent_conversations,
        'continuous_mode_active': True,
        'go_live_state': 'accepted-continuous-mode-active',
        'accepted_by': payload.actor,
        'accepted_at': accepted_at,
        'paused_at': None,
        'pause_reason': None,
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
    }
    _go_live_store[payload.telegram_chat_id] = record
    return {
        'state': 'telegram-operational-go-live-accepted',
        'acceptance': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-continuous-conversation-supervisor',
    }


@router.post('/pause')
def pause_continuous_mode(payload: TelegramContinuousModePauseRequest) -> dict:
    if payload.pause_phrase != _PAUSE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram continuous-mode pause approval required')
    record = _go_live_store.get(payload.telegram_chat_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Active Telegram go-live acceptance not found')
    if not record.get('continuous_mode_active'):
        return {'state': 'telegram-continuous-mode-already-paused', 'acceptance': record, 'idempotent_replay': True, 'external_calls_made': 0}

    record['continuous_mode_active'] = False
    record['go_live_state'] = 'paused-by-operator'
    record['paused_by'] = payload.actor
    record['paused_at'] = datetime.now(timezone.utc).isoformat()
    record['pause_reason'] = payload.reason
    return {'state': 'telegram-continuous-mode-paused', 'acceptance': record, 'external_calls_made': 0}


@router.get('/status')
def go_live_status() -> dict:
    active = [item for item in _go_live_store.values() if item.get('continuous_mode_active')]
    return {
        'go_live_acceptances': len(_go_live_store),
        'active_continuous_chats': len(active),
        'paused_chats': len(_go_live_store) - len(active),
        'continuous_mode_active': bool(active),
        'external_calls_made': 0,
        'mode': 'validated-operator-controlled-continuous-conversation',
    }


@router.get('/acceptances')
def list_go_live_acceptances() -> dict:
    items = sorted(_go_live_store.values(), key=lambda item: item['accepted_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_phone_validation_reconciliation_v21_321 import command_center as v21_321_command_center

    html = v21_321_command_center().replace('v21.321', 'v21.322')
    return html.replace(
        'AURON TELEGRAM PHONE VALIDATION RECONCILIATION COMMAND CENTER',
        'AURON TELEGRAM OPERATIONAL GO LIVE ACCEPTANCE COMMAND CENTER',
    )
