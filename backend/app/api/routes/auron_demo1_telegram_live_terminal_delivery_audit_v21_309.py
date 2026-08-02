from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_live_delivery_state_commit_v21_305 import _live_delivery_commit_store
from app.api.routes.auron_demo1_telegram_live_retry_receipt_commit_v21_308 import _live_retry_commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store

router = APIRouter(prefix='/auron/demo1/v21.309', tags=['auron-demo1-telegram-live-terminal-delivery-audit'])

_live_terminal_audit_store: dict[str, dict] = {}
_AUDIT_VERSION = 'v21.309'
_TERMINAL_STATES = {'delivered', 'permanent-failure', 'retry-exhausted'}


class TelegramLiveTerminalAuditRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


def reset_telegram_live_terminal_delivery_audit_store() -> None:
    _live_terminal_audit_store.clear()


def _original_commit(correlation_id: str) -> dict | None:
    return next((item for item in _live_delivery_commit_store.values() if item.get('correlation_id') == correlation_id), None)


def _retry_commits(correlation_id: str) -> list[dict]:
    return sorted(
        (item for item in _live_retry_commit_store.values() if item.get('correlation_id') == correlation_id),
        key=lambda item: (int(item.get('attempt', 0)), item.get('committed_at', '')),
    )


def _integrity_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(canonical.encode('utf-8')).hexdigest()


@router.get('/status')
def telegram_live_terminal_audit_status() -> dict:
    return {
        'live_terminal_audits': len(_live_terminal_audit_store),
        'integrity_verified': sum(1 for item in _live_terminal_audit_store.values() if item['integrity_verified']),
        'immutable_receipts': sum(1 for item in _live_terminal_audit_store.values() if item['immutable']),
        'external_calls_made': 0,
        'audit_mode': 'immutable-live-delivery-chain-receipt',
    }


@router.post('/audit')
def audit_live_terminal_delivery(payload: TelegramLiveTerminalAuditRequest) -> dict:
    existing = _live_terminal_audit_store.get(payload.correlation_id)
    if existing is not None:
        return {
            'state': 'telegram-live-terminal-delivery-already-audited',
            'audit': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    original = _original_commit(payload.correlation_id)
    retries = _retry_commits(payload.correlation_id)
    outbound = _outbound_store.get(payload.correlation_id)
    if original is None or outbound is None:
        raise HTTPException(status_code=409, detail='Original live delivery commit and correlated outbound required')

    terminal_source = retries[-1] if retries else original
    final_state = terminal_source.get('delivery_state')
    checks = {
        'original_commit_present': original is not None,
        'outbound_present': outbound is not None,
        'original_correlation_matches': original.get('correlation_id') == payload.correlation_id,
        'outbound_correlation_matches': outbound.get('correlation_id') == payload.correlation_id,
        'outbound_id_matches': outbound.get('outbound_id') == original.get('outbound_id'),
        'terminal_source_is_terminal': terminal_source.get('terminal') is True,
        'terminal_state_supported': final_state in _TERMINAL_STATES,
        'outbound_state_matches_terminal_source': outbound.get('delivery_state') == final_state,
        'retry_chain_ordered': all(
            int(item.get('attempt', 0)) == index
            for index, item in enumerate(retries, start=2)
        ),
        'retry_chain_correlated': all(
            item.get('live_delivery_commit_id') == original.get('live_delivery_commit_id')
            and item.get('outbound_id') == original.get('outbound_id')
            and item.get('provider_id') == original.get('provider_id')
            and item.get('runtime_id') == original.get('runtime_id')
            for item in retries
        ),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'telegram-live-terminal-delivery-audit-blocked',
            'correlation_id': payload.correlation_id,
            'checks': checks,
            'blockers': blockers,
            'external_calls_made': 0,
            'next_layer': 'telegram-live-delivery-chain-remediation',
        }

    chain = {
        'correlation_id': payload.correlation_id,
        'original_live_delivery_commit_id': original['live_delivery_commit_id'],
        'original_execution_id': original['execution_id'],
        'activation_id': original['activation_id'],
        'provider_id': original['provider_id'],
        'runtime_id': original['runtime_id'],
        'outbound_id': original['outbound_id'],
        'dispatch_id': original['dispatch_id'],
        'original_delivery_state': original['delivery_state'],
        'retry_attempts': [
            {
                'attempt': item['attempt'],
                'live_retry_id': item['live_retry_id'],
                'live_retry_dispatch_id': item['live_retry_dispatch_id'],
                'live_retry_receipt_id': item['live_retry_receipt_id'],
                'live_retry_delivery_commit_id': item['live_retry_delivery_commit_id'],
                'delivery_state': item['delivery_state'],
                'http_status': item['http_status'],
                'provider_message_id': item.get('provider_message_id'),
                'provider_error': item.get('provider_error'),
            }
            for item in retries
        ],
        'final_delivery_state': final_state,
        'final_attempt': terminal_source.get('attempt', 1),
        'provider_message_id': terminal_source.get('provider_message_id'),
        'provider_error': terminal_source.get('provider_error'),
    }
    audit_id = str(uuid4())
    audited_at = datetime.now(timezone.utc).isoformat()
    record = {
        'live_terminal_audit_id': audit_id,
        **chain,
        'integrity_hash': _integrity_hash(chain),
        'integrity_verified': True,
        'immutable': True,
        'chain_complete': True,
        'audit_version': _AUDIT_VERSION,
        'audited_by': payload.actor,
        'audited_at': audited_at,
        'note': payload.note,
    }
    _live_terminal_audit_store[payload.correlation_id] = record
    outbound['live_terminal_audit_id'] = audit_id
    outbound['live_terminal_integrity_hash'] = record['integrity_hash']
    outbound['live_terminal_audited_at'] = audited_at

    return {
        'state': 'telegram-live-terminal-delivery-audited',
        'audit': record,
        'checks': checks,
        'external_calls_made': 0,
        'next_layer': 'telegram-live-lifecycle-closure',
    }


@router.get('/audits')
def list_live_terminal_audits() -> dict:
    items = sorted(_live_terminal_audit_store.values(), key=lambda item: item['audited_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_live_retry_receipt_commit_v21_308 import command_center as v21_308_command_center

    html = v21_308_command_center()
    html = html.replace('v21.308', 'v21.309')
    return html.replace(
        'AURON TELEGRAM LIVE RETRY RECEIPT COMMIT COMMAND CENTER',
        'AURON TELEGRAM LIVE TERMINAL DELIVERY AUDIT COMMAND CENTER',
    )
