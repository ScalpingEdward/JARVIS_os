from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_delivery_state_commit_v21_296 import _commit_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store
from app.api.routes.auron_demo1_telegram_retry_delivery_state_commit_v21_300 import _retry_delivery_commit_store
from app.api.routes.auron_demo1_telegram_terminal_delivery_audit_v21_301 import _audit_store

router = APIRouter(prefix='/auron/demo1/v21.302', tags=['auron-demo1-telegram-lifecycle-closure'])

_closure_store: dict[str, dict] = {}
_CLOSURE_VERSION = 'v21.302'
_TERMINAL_STATES = {'delivered', 'permanent-failure', 'retry-exhausted'}


class TelegramLifecycleClosureRequest(BaseModel):
    correlation_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    archive: bool = True
    note: str | None = Field(default=None, max_length=500)


def reset_telegram_lifecycle_closure_store() -> None:
    _closure_store.clear()


def _latest_retry_commit(correlation_id: str) -> dict | None:
    items = [item for item in _retry_delivery_commit_store.values() if item['correlation_id'] == correlation_id]
    return max(items, key=lambda item: item['committed_at']) if items else None


def _chain_checks(original_commit: dict, retry_commit: dict | None, outbound: dict, audit: dict) -> dict[str, bool]:
    source = retry_commit or original_commit
    return {
        'audit_present': bool(audit),
        'audit_immutable': audit.get('immutable') is True,
        'audit_integrity_verified': audit.get('integrity_verified') is True,
        'audit_terminal': audit.get('terminal') is True,
        'terminal_state_supported': source.get('delivery_state') in _TERMINAL_STATES,
        'source_terminal': source.get('terminal') is True,
        'audit_state_matches_source': audit.get('delivery_state') == source.get('delivery_state'),
        'audit_original_commit_matches': audit.get('original_commit_id') == original_commit.get('commit_id'),
        'audit_retry_commit_matches': audit.get('retry_delivery_commit_id') == (
            retry_commit.get('retry_delivery_commit_id') if retry_commit else None
        ),
        'audit_outbound_matches': audit.get('outbound_id') == outbound.get('outbound_id'),
        'outbound_state_matches_source': outbound.get('delivery_state') == source.get('delivery_state'),
        'correlation_matches': all(
            item.get('correlation_id') == original_commit.get('correlation_id')
            for item in (outbound, audit)
        ) and (retry_commit is None or retry_commit.get('correlation_id') == original_commit.get('correlation_id')),
    }


@router.get('/status')
def telegram_lifecycle_closure_status() -> dict:
    return {
        'closed_lifecycles': len(_closure_store),
        'archived_lifecycles': sum(1 for item in _closure_store.values() if item['archived']),
        'closure_version': _CLOSURE_VERSION,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'closure_mode': 'verified-terminal-chain-closure',
    }


@router.post('/close')
def close_telegram_lifecycle(payload: TelegramLifecycleClosureRequest) -> dict:
    existing = _closure_store.get(payload.correlation_id)
    if existing is not None:
        return {
            'state': 'telegram-lifecycle-already-closed',
            'closure': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    original_commit = _commit_store.get(payload.correlation_id)
    outbound = _outbound_store.get(payload.correlation_id)
    audit = _audit_store.get(payload.correlation_id)
    retry_commit = _latest_retry_commit(payload.correlation_id)
    if original_commit is None or outbound is None or audit is None:
        raise HTTPException(status_code=409, detail='Complete audited Telegram lifecycle chain required')

    checks = _chain_checks(original_commit, retry_commit, outbound, audit)
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'telegram-lifecycle-closure-blocked',
            'correlation_id': payload.correlation_id,
            'checks': checks,
            'blockers': blockers,
            'provider_api_calls_made': 0,
            'external_calls_made': 0,
            'next_layer': 'telegram-lifecycle-integrity-remediation',
        }

    source = retry_commit or original_commit
    closed_at = datetime.now(timezone.utc).isoformat()
    record = {
        'closure_id': str(uuid4()),
        'correlation_id': payload.correlation_id,
        'audit_id': audit['audit_id'],
        'original_commit_id': original_commit['commit_id'],
        'retry_delivery_commit_id': retry_commit.get('retry_delivery_commit_id') if retry_commit else None,
        'outbound_id': outbound['outbound_id'],
        'delivery_state': source['delivery_state'],
        'provider_message_id': source.get('provider_message_id'),
        'attempt': source.get('attempt', original_commit.get('attempt')),
        'max_attempts': source.get('max_attempts', original_commit.get('max_attempts')),
        'integrity_hash': audit['integrity_hash'],
        'chain_complete': True,
        'lifecycle_closed': True,
        'archived': payload.archive,
        'immutable_audit_preserved': True,
        'closed_by': payload.actor,
        'closed_at': closed_at,
        'closure_version': _CLOSURE_VERSION,
        'note': payload.note,
    }
    _closure_store[payload.correlation_id] = record
    original_commit['lifecycle_closed'] = True
    original_commit['lifecycle_closure_id'] = record['closure_id']
    original_commit['lifecycle_closed_at'] = closed_at
    outbound['lifecycle_closed'] = True
    outbound['lifecycle_closure_id'] = record['closure_id']
    outbound['archived'] = payload.archive
    audit['lifecycle_closure_id'] = record['closure_id']

    return {
        'state': 'telegram-lifecycle-closed',
        'closure': record,
        'checks': checks,
        'provider_api_calls_made': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-production-transport-activation-gate',
        'reply': 'Der Telegram-Lebenszyklus wurde vollstaendig geprueft, geschlossen und intern archiviert.',
    }


@router.get('/closures')
def list_telegram_lifecycle_closures() -> dict:
    items = sorted(_closure_store.values(), key=lambda item: item['closed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_terminal_delivery_audit_v21_301 import command_center as v21_301_command_center

    html = v21_301_command_center()
    html = html.replace('v21.301', 'v21.302')
    html = html.replace(
        'AURON TELEGRAM TERMINAL DELIVERY AUDIT COMMAND CENTER',
        'AURON TELEGRAM LIFECYCLE CLOSURE COMMAND CENTER',
    )
    return html
