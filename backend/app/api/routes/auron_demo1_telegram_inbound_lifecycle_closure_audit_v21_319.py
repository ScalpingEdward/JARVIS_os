from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_correlated_response_controlled_execution_v21_317 import _execution_handoff_store
from app.api.routes.auron_demo1_telegram_correlated_response_delivery_admission_v21_316 import _admission_store
from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import _dispatch_store
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _message_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _outbound_store
from app.api.routes.auron_demo1_telegram_runtime_result_correlation_v21_318 import _result_commit_store

router = APIRouter(prefix='/auron/demo1/v21.319', tags=['auron-demo1-telegram-inbound-lifecycle-closure-audit'])

_closure_audit_store: dict[str, dict] = {}
_TERMINAL_STATES = {'delivered', 'permanent-failure'}


class TelegramInboundLifecycleClosureRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    archive: bool = True


def reset_telegram_inbound_lifecycle_closure_audit_store() -> None:
    _closure_audit_store.clear()


def _integrity_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/close')
def close_inbound_lifecycle(payload: TelegramInboundLifecycleClosureRequest) -> dict:
    existing = _closure_audit_store.get(payload.update_id)
    if existing is not None:
        return {
            'state': 'telegram-inbound-lifecycle-already-closed',
            'closure': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    commit = _result_commit_store.get(payload.update_id)
    handoff = _execution_handoff_store.get(payload.update_id)
    admission = _admission_store.get(payload.update_id)
    dispatch = _dispatch_store.get(payload.update_id)
    message = _message_store.get(payload.update_id)
    if not all((commit, handoff, admission, dispatch, message)):
        raise HTTPException(status_code=404, detail='Complete Telegram inbound lifecycle required')

    terminal_state = commit.get('delivery_state')
    if terminal_state not in _TERMINAL_STATES:
        raise HTTPException(status_code=409, detail='Telegram inbound lifecycle is not terminal; retry handling must complete first')

    outbound = _outbound_store.get(commit['correlation_id'])
    checks = {
        'outbound_present': outbound is not None,
        'commit_handoff_matches': commit.get('handoff_id') == handoff.get('handoff_id'),
        'commit_admission_matches': commit.get('admission_id') == admission.get('admission_id'),
        'commit_dispatch_matches': commit.get('dispatch_id') == dispatch.get('dispatch_id'),
        'commit_outbound_matches': bool(outbound and commit.get('outbound_id') == outbound.get('outbound_id')),
        'execution_matches': commit.get('execution_id') == handoff.get('execution_id') == admission.get('execution_id') == dispatch.get('live_execution_id'),
        'correlation_matches': bool(outbound and commit.get('correlation_id') == dispatch.get('correlation_id') == outbound.get('correlation_id')),
        'terminal_state_matches': bool(outbound and terminal_state == dispatch.get('dispatch_state') == admission.get('admission_state') == outbound.get('delivery_state') == message.get('delivery_state')),
        'provider_message_matches': bool(outbound and commit.get('provider_message_id') == dispatch.get('provider_message_id') == outbound.get('provider_message_id') == message.get('provider_message_id')),
        'delivery_flag_matches': bool(outbound and dispatch.get('reply_sent') == (terminal_state == 'delivered') and outbound.get('message_sent') == (terminal_state == 'delivered') and message.get('reply_sent') == (terminal_state == 'delivered')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram inbound lifecycle closure chain is inconsistent', 'blockers': blockers})

    audit_payload = {
        'update_id': payload.update_id,
        'result_commit_id': commit['result_commit_id'],
        'execution_id': commit['execution_id'],
        'worker_run_id': commit['worker_run_id'],
        'receipt_id': commit['receipt_id'],
        'handoff_id': commit['handoff_id'],
        'admission_id': commit['admission_id'],
        'dispatch_id': commit['dispatch_id'],
        'correlation_id': commit['correlation_id'],
        'outbound_id': commit['outbound_id'],
        'terminal_state': terminal_state,
        'provider_message_id': commit.get('provider_message_id'),
        'provider_error': commit.get('provider_error'),
        'http_status': commit.get('http_status'),
        'checks': checks,
    }
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'closure_id': str(uuid4()),
        **audit_payload,
        'integrity_hash': _integrity_hash(audit_payload),
        'integrity_algorithm': 'sha256',
        'immutable': True,
        'chain_complete': True,
        'archived': payload.archive,
        'closed_by': payload.actor,
        'closed_at': now,
        'external_calls_made': 0,
    }
    _closure_audit_store[payload.update_id] = record

    handoff.update(handoff_state='lifecycle-closed', closure_id=record['closure_id'])
    admission.update(admission_state=f'{terminal_state}-closed', closure_id=record['closure_id'])
    dispatch.update(dispatch_state=f'{terminal_state}-closed', closure_id=record['closure_id'])
    outbound.update(delivery_state=f'{terminal_state}-closed', closure_id=record['closure_id'])
    message.update(delivery_state=f'{terminal_state}-closed', closure_id=record['closure_id'])

    return {
        'state': 'telegram-inbound-lifecycle-closed-and-audited',
        'closure': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-inbound-operational-readiness-and-observability',
    }


@router.get('/status')
def closure_audit_status() -> dict:
    return {
        'closures': len(_closure_audit_store),
        'delivered_closed': sum(1 for item in _closure_audit_store.values() if item['terminal_state'] == 'delivered'),
        'failed_closed': sum(1 for item in _closure_audit_store.values() if item['terminal_state'] == 'permanent-failure'),
        'immutable_records': sum(1 for item in _closure_audit_store.values() if item['immutable']),
        'external_calls_made': 0,
        'closure_mode': 'immutable-terminal-inbound-lifecycle-audit',
    }


@router.get('/closures')
def list_closure_audits() -> dict:
    items = sorted(_closure_audit_store.values(), key=lambda item: item['closed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_runtime_result_correlation_v21_318 import command_center as v21_318_command_center
    html = v21_318_command_center().replace('v21.318', 'v21.319')
    return html.replace('AURON TELEGRAM RUNTIME RESULT CORRELATION COMMAND CENTER', 'AURON TELEGRAM INBOUND LIFECYCLE CLOSURE AUDIT COMMAND CENTER')
