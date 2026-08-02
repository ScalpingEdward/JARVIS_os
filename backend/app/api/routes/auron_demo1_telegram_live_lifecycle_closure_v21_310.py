from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_live_terminal_delivery_audit_v21_309 import _live_terminal_audit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.310', tags=['auron-demo1-telegram-live-lifecycle-closure'])

_live_lifecycle_closure_store: dict[str, dict] = {}
_CLOSURE_VERSION = 'v21.310'


class TelegramLiveLifecycleClosureRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    archive: bool = True
    note: str | None = Field(default=None, max_length=500)


def reset_telegram_live_lifecycle_closure_store() -> None:
    _live_lifecycle_closure_store.clear()


@router.get('/status')
def telegram_live_lifecycle_closure_status() -> dict:
    return {
        'closed_live_lifecycles': len(_live_lifecycle_closure_store),
        'archived_live_lifecycles': sum(1 for item in _live_lifecycle_closure_store.values() if item['archived']),
        'external_calls_made': 0,
        'closure_mode': 'verified-live-delivery-lifecycle-closure',
    }


@router.post('/close')
def close_telegram_live_lifecycle(payload: TelegramLiveLifecycleClosureRequest) -> dict:
    existing = _live_lifecycle_closure_store.get(payload.correlation_id)
    if existing is not None:
        return {'state': 'telegram-live-lifecycle-already-closed', 'closure': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    audit = _live_terminal_audit_store.get(payload.correlation_id)
    outbound = _outbound_store.get(payload.correlation_id)
    if audit is None or outbound is None:
        raise HTTPException(status_code=409, detail='Immutable live terminal audit and correlated outbound required')

    checks = {
        'audit_immutable': audit.get('immutable') is True,
        'audit_integrity_verified': audit.get('integrity_verified') is True,
        'audit_chain_complete': audit.get('chain_complete') is True,
        'audit_correlation_matches': audit.get('correlation_id') == payload.correlation_id,
        'outbound_correlation_matches': outbound.get('correlation_id') == payload.correlation_id,
        'outbound_id_matches': outbound.get('outbound_id') == audit.get('outbound_id'),
        'outbound_state_matches': outbound.get('delivery_state') == audit.get('final_delivery_state'),
        'outbound_audit_matches': outbound.get('live_terminal_audit_id') == audit.get('live_terminal_audit_id'),
        'outbound_integrity_hash_matches': outbound.get('live_terminal_integrity_hash') == audit.get('integrity_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'telegram-live-lifecycle-closure-blocked',
            'correlation_id': payload.correlation_id,
            'checks': checks,
            'blockers': blockers,
            'external_calls_made': 0,
            'next_layer': 'telegram-live-lifecycle-integrity-remediation',
        }

    closure_id = str(uuid4())
    closed_at = datetime.now(timezone.utc).isoformat()
    record = {
        'live_lifecycle_closure_id': closure_id,
        'correlation_id': payload.correlation_id,
        'live_terminal_audit_id': audit['live_terminal_audit_id'],
        'integrity_hash': audit['integrity_hash'],
        'final_delivery_state': audit['final_delivery_state'],
        'final_attempt': audit['final_attempt'],
        'provider_id': audit['provider_id'],
        'runtime_id': audit['runtime_id'],
        'outbound_id': audit['outbound_id'],
        'chain_complete': True,
        'lifecycle_closed': True,
        'archived': payload.archive,
        'closure_version': _CLOSURE_VERSION,
        'closed_by': payload.actor,
        'closed_at': closed_at,
        'note': payload.note,
    }
    _live_lifecycle_closure_store[payload.correlation_id] = record
    outbound['live_lifecycle_closed'] = True
    outbound['live_lifecycle_closure_id'] = closure_id
    outbound['live_lifecycle_closed_at'] = closed_at
    outbound['archived'] = payload.archive

    return {
        'state': 'telegram-live-lifecycle-closed',
        'closure': record,
        'checks': checks,
        'external_calls_made': 0,
        'next_layer': 'telegram-operational-runtime-worker-integration',
        'reply': 'Der Telegram-Live-Lebenszyklus wurde vollstaendig geprueft, geschlossen und archiviert.',
    }


@router.get('/closures')
def list_telegram_live_lifecycle_closures() -> dict:
    items = sorted(_live_lifecycle_closure_store.values(), key=lambda item: item['closed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_live_terminal_delivery_audit_v21_309 import command_center as v21_309_command_center

    html = v21_309_command_center()
    html = html.replace('v21.309', 'v21.310')
    return html.replace(
        'AURON TELEGRAM LIVE TERMINAL DELIVERY AUDIT COMMAND CENTER',
        'AURON TELEGRAM LIVE LIFECYCLE CLOSURE COMMAND CENTER',
    )
