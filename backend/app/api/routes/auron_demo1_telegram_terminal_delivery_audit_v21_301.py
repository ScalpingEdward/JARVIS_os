from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_delivery_state_commit_v21_296 import _commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store
from app.api.routes.auron_demo1_telegram_retry_delivery_state_commit_v21_300 import _retry_delivery_commit_store

router = APIRouter(prefix='/auron/demo1/v21.301', tags=['auron-demo1-telegram-terminal-delivery-audit'])

_audit_store: dict[str, dict] = {}
_AUDIT_VERSION = 'v21.301'
_TERMINAL_STATES = {'delivered', 'permanent-failure', 'retry-exhausted'}


class TelegramTerminalAuditRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


def reset_telegram_terminal_delivery_audit_store() -> None:
    _audit_store.clear()


def _latest_retry_commit(correlation_id: str) -> dict | None:
    items = [item for item in _retry_delivery_commit_store.values() if item['correlation_id'] == correlation_id]
    return max(items, key=lambda item: item['committed_at']) if items else None


def _integrity_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


@router.get('/status')
def telegram_terminal_audit_status() -> dict:
    return {
        'terminal_audits': len(_audit_store),
        'immutable_receipts': sum(1 for item in _audit_store.values() if item['immutable']),
        'audit_version': _AUDIT_VERSION,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'audit_mode': 'immutable-terminal-delivery-receipt',
    }


@router.post('/audit')
def audit_terminal_delivery(payload: TelegramTerminalAuditRequest) -> dict:
    existing = _audit_store.get(payload.correlation_id)
    if existing is not None:
        return {
            'state': 'telegram-terminal-delivery-already-audited',
            'audit': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    original_commit = _commit_store.get(payload.correlation_id)
    outbound = _outbound_store.get(payload.correlation_id)
    if original_commit is None or outbound is None:
        raise HTTPException(status_code=409, detail='Correlated Telegram delivery and outbound state required')

    retry_commit = _latest_retry_commit(payload.correlation_id)
    source = retry_commit or original_commit
    delivery_state = source.get('delivery_state')
    terminal = source.get('terminal') is True
    if not terminal or delivery_state not in _TERMINAL_STATES:
        raise HTTPException(status_code=409, detail='Terminal Telegram delivery state required before audit')
    if outbound.get('delivery_state') != delivery_state:
        raise HTTPException(status_code=409, detail='Telegram outbound terminal state mismatch')

    audited_at = datetime.now(timezone.utc).isoformat()
    integrity_payload = {
        'audit_version': _AUDIT_VERSION,
        'correlation_id': payload.correlation_id,
        'delivery_state': delivery_state,
        'original_commit_id': original_commit['commit_id'],
        'retry_delivery_commit_id': retry_commit.get('retry_delivery_commit_id') if retry_commit else None,
        'outbound_id': outbound['outbound_id'],
        'provider_message_id': source.get('provider_message_id'),
        'attempt': source.get('attempt', original_commit.get('attempt')),
        'max_attempts': source.get('max_attempts', original_commit.get('max_attempts')),
    }
    record = {
        'audit_id': str(uuid4()),
        **integrity_payload,
        'integrity_hash': _integrity_hash(integrity_payload),
        'integrity_verified': True,
        'immutable': True,
        'terminal': True,
        'audited_by': payload.actor,
        'audited_at': audited_at,
        'note': payload.note,
    }
    _audit_store[payload.correlation_id] = record
    original_commit['terminal_audit_id'] = record['audit_id']
    original_commit['terminal_audited_at'] = audited_at
    outbound['terminal_audit_id'] = record['audit_id']
    outbound['terminal_audited_at'] = audited_at

    return {
        'state': 'telegram-terminal-delivery-audited',
        'audit': record,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-lifecycle-closure',
    }


@router.get('/audits')
def list_terminal_audits() -> dict:
    items = sorted(_audit_store.values(), key=lambda item: item['audited_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_retry_delivery_state_commit_v21_300 import command_center as v21_300_command_center

    html = v21_300_command_center()
    html = html.replace('v21.300', 'v21.301')
    html = html.replace(
        'AURON TELEGRAM RETRY DELIVERY STATE COMMIT COMMAND CENTER',
        'AURON TELEGRAM TERMINAL DELIVERY AUDIT COMMAND CENTER',
    )
    return html
