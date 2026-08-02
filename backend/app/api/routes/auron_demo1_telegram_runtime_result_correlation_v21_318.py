from __future__ import annotations

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

router = APIRouter(prefix='/auron/demo1/v21.318', tags=['auron-demo1-telegram-runtime-result-correlation'])
_result_commit_store: dict[str, dict] = {}


class TelegramRuntimeResultCorrelationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    update_id: str = Field(min_length=1, max_length=120)
    execution_id: str = Field(min_length=1, max_length=160)


def reset_telegram_runtime_result_correlation_store() -> None:
    _result_commit_store.clear()


def _delivery_state(run: dict) -> str:
    if run.get('accepted'):
        return 'delivered'
    status = int(run.get('http_status') or 0)
    error = str(run.get('provider_error') or '').lower()
    if status == 429 or status >= 500 or status in {408, 425} or 'timeout' in error or 'network' in error:
        return 'retry-required'
    return 'permanent-failure'


@router.post('/commit')
def commit_runtime_result(payload: TelegramRuntimeResultCorrelationRequest) -> dict:
    existing = _result_commit_store.get(payload.update_id)
    if existing is not None:
        if existing['execution_id'] != payload.execution_id:
            raise HTTPException(status_code=409, detail='Telegram update already committed with a different execution')
        return {'state': 'telegram-runtime-result-already-correlated', 'commit': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    # Function-local import prevents the composite v21.311 router from forming a
    # circular import when it includes this module during app startup.
    from app.api.routes.auron_demo1_telegram_operational_runtime_worker_v21_311 import _worker_run_store

    handoff = _execution_handoff_store.get(payload.update_id)
    admission = _admission_store.get(payload.update_id)
    dispatch = _dispatch_store.get(payload.update_id)
    message = _message_store.get(payload.update_id)
    run = _worker_run_store.get(payload.execution_id)
    if handoff is None or admission is None or dispatch is None or message is None:
        raise HTTPException(status_code=404, detail='Complete correlated Telegram inbound lifecycle not found')
    if run is None:
        raise HTTPException(status_code=404, detail='Telegram runtime-worker result not found')

    outbound = _outbound_store.get(dispatch['correlation_id'])
    checks = {
        'handoff_execution_matches': handoff.get('execution_id') == payload.execution_id,
        'admission_execution_matches': admission.get('execution_id') == payload.execution_id,
        'dispatch_execution_matches': dispatch.get('live_execution_id') == payload.execution_id,
        'worker_correlation_matches': run.get('correlation_id') == dispatch.get('correlation_id'),
        'outbound_present': outbound is not None,
        'outbound_execution_matches': bool(outbound and outbound.get('live_execution_id') == payload.execution_id),
        'outbound_id_matches': bool(outbound and outbound.get('outbound_id') == dispatch.get('outbound_id')),
        'chat_matches': bool(outbound and str(outbound.get('telegram_chat_id')) == str(dispatch.get('telegram_chat_id'))),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram runtime result correlation is inconsistent', 'blockers': blockers})

    delivery_state = _delivery_state(run)
    delivered = delivery_state == 'delivered'
    record = {
        'result_commit_id': str(uuid4()), 'update_id': payload.update_id,
        'execution_id': payload.execution_id, 'worker_run_id': run['worker_run_id'],
        'receipt_id': run['receipt_id'], 'handoff_id': handoff['handoff_id'],
        'admission_id': admission['admission_id'], 'dispatch_id': dispatch['dispatch_id'],
        'correlation_id': dispatch['correlation_id'], 'outbound_id': dispatch['outbound_id'],
        'delivery_state': delivery_state, 'provider_message_id': run.get('provider_message_id'),
        'provider_error': run.get('provider_error'), 'http_status': run.get('http_status'),
        'checks': checks, 'committed_by': payload.actor,
        'committed_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0,
    }
    _result_commit_store[payload.update_id] = record
    handoff.update(handoff_state='runtime-result-correlated', result_commit_id=record['result_commit_id'])
    admission.update(admission_state='delivered' if delivered else delivery_state, result_commit_id=record['result_commit_id'])
    dispatch.update(dispatch_state='delivered' if delivered else delivery_state, reply_sent=delivered, provider_message_id=run.get('provider_message_id'), result_commit_id=record['result_commit_id'])
    outbound.update(delivery_state=delivery_state, message_sent=delivered, provider_message_id=run.get('provider_message_id'), result_commit_id=record['result_commit_id'])
    message.update(reply_sent=delivered, delivery_state=delivery_state, provider_message_id=run.get('provider_message_id'))
    return {'state': 'telegram-runtime-result-correlated-and-committed', 'commit': record, 'outbound_messages_sent': 1 if delivered else 0, 'external_calls_made': 0, 'next_layer': 'telegram-inbound-conversation-lifecycle-closure' if delivered else 'telegram-correlated-response-retry-or-failure-handling'}


@router.get('/status')
def runtime_result_correlation_status() -> dict:
    return {'result_commits': len(_result_commit_store), 'delivered': sum(1 for item in _result_commit_store.values() if item['delivery_state'] == 'delivered'), 'retry_required': sum(1 for item in _result_commit_store.values() if item['delivery_state'] == 'retry-required'), 'permanent_failures': sum(1 for item in _result_commit_store.values() if item['delivery_state'] == 'permanent-failure'), 'external_calls_made': 0, 'correlation_mode': 'runtime-result-to-inbound-lifecycle-commit'}


@router.get('/commits')
def list_runtime_result_commits() -> dict:
    items = sorted(_result_commit_store.values(), key=lambda item: item['committed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_correlated_response_controlled_execution_v21_317 import command_center as v21_317_command_center
    html = v21_317_command_center().replace('v21.317', 'v21.318')
    return html.replace('AURON TELEGRAM CORRELATED RESPONSE CONTROLLED EXECUTION COMMAND CENTER', 'AURON TELEGRAM RUNTIME RESULT CORRELATION COMMAND CENTER')
