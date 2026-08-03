from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import _dispatch_store
from app.api.routes.auron_demo1_telegram_inbound_lifecycle_closure_audit_v21_319 import _closure_audit_store
from app.api.routes.auron_demo1_telegram_inbound_webhook_receiver_v21_314 import _webhook_receipt_store
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _message_store
from app.api.routes.auron_demo1_telegram_operational_readiness_observability_v21_320 import _validation_run_store
from app.api.routes.auron_demo1_telegram_runtime_result_correlation_v21_318 import _result_commit_store

router = APIRouter(prefix='/auron/demo1/v21.321', tags=['auron-demo1-telegram-phone-validation-reconciliation'])

_reconciliation_store: dict[str, dict] = {}


class TelegramPhoneValidationReconcileRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    validation_run_id: str = Field(min_length=1, max_length=160)
    update_id: str = Field(min_length=1, max_length=120)
    phone_reply_observed: bool = False
    observed_provider_message_id: str | None = Field(default=None, max_length=160)


def reset_telegram_phone_validation_reconciliation_store() -> None:
    _reconciliation_store.clear()


def _validation_run_by_id(validation_run_id: str) -> dict | None:
    return next((item for item in _validation_run_store.values() if item.get('validation_run_id') == validation_run_id), None)


def _integrity_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/reconcile')
def reconcile_phone_validation(payload: TelegramPhoneValidationReconcileRequest) -> dict:
    existing = _reconciliation_store.get(payload.validation_run_id)
    if existing is not None:
        if existing.get('update_id') != payload.update_id:
            raise HTTPException(status_code=409, detail='Validation run already reconciled with another Telegram update')
        return {
            'state': 'telegram-phone-validation-already-reconciled',
            'reconciliation': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    run = _validation_run_by_id(payload.validation_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram phone-validation run not found')
    if run.get('run_state') not in {'prepared-awaiting-phone-message', 'evidence-captured-awaiting-reconciliation'}:
        raise HTTPException(status_code=409, detail='Telegram phone-validation run is not awaiting reconciliation')

    receipt = _webhook_receipt_store.get(payload.update_id)
    message = _message_store.get(payload.update_id)
    dispatch = _dispatch_store.get(payload.update_id)
    result_commit = _result_commit_store.get(payload.update_id)
    closure = _closure_audit_store.get(payload.update_id)

    expected_message = str(run.get('test_message') or '').strip()
    observed_message = str((message or {}).get('text') or '').strip()
    provider_message_id = (result_commit or {}).get('provider_message_id')
    closure_state = (closure or {}).get('terminal_state') or (closure or {}).get('delivery_state')

    checks = {
        'webhook_receipt_present': receipt is not None,
        'webhook_secret_verified': bool(receipt and receipt.get('secret_verified')),
        'inbound_message_present': message is not None,
        'test_message_matches': bool(message and observed_message == expected_message),
        'chat_matches': bool(message and str(message.get('telegram_chat_id')) == str(run.get('telegram_chat_id'))),
        'operator_matches': bool(message and message.get('operator_id') == run.get('operator_id')),
        'workspace_matches': bool(message and message.get('workspace_id') == run.get('workspace_id')),
        'conversation_dispatched': dispatch is not None,
        'result_correlated': result_commit is not None,
        'delivery_succeeded': bool(result_commit and result_commit.get('delivery_state') == 'delivered'),
        'lifecycle_closed': closure is not None,
        'closure_terminal_delivered': closure_state in {'delivered', None} and bool(closure),
        'phone_reply_observed': payload.phone_reply_observed,
        'provider_message_id_present': bool(provider_message_id),
        'observed_provider_message_matches': payload.observed_provider_message_id is None or str(payload.observed_provider_message_id) == str(provider_message_id),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    passed = not blockers
    reconciled_at = datetime.now(timezone.utc).isoformat()
    audit_payload = {
        'validation_run_id': payload.validation_run_id,
        'update_id': payload.update_id,
        'readiness_id': run.get('readiness_id'),
        'telegram_chat_id': run.get('telegram_chat_id'),
        'operator_id': run.get('operator_id'),
        'workspace_id': run.get('workspace_id'),
        'webhook_receipt_id': (receipt or {}).get('webhook_receipt_id'),
        'dispatch_id': (dispatch or {}).get('dispatch_id'),
        'result_commit_id': (result_commit or {}).get('result_commit_id'),
        'closure_id': (closure or {}).get('closure_id'),
        'provider_message_id': provider_message_id,
        'checks': checks,
        'result': 'passed' if passed else 'failed',
    }
    record = {
        'reconciliation_id': str(uuid4()),
        **audit_payload,
        'blockers': blockers,
        'validation_passed': passed,
        'reconciliation_state': 'passed' if passed else 'failed',
        'integrity_hash': _integrity_hash(audit_payload),
        'immutable': True,
        'reconciled_by': payload.actor,
        'reconciled_at': reconciled_at,
        'external_calls_made': 0,
    }
    _reconciliation_store[payload.validation_run_id] = record
    run['run_state'] = 'passed' if passed else 'failed'
    run['reconciliation_id'] = record['reconciliation_id']
    run['update_id'] = payload.update_id
    run['completed_at'] = reconciled_at

    return {
        'state': 'telegram-phone-validation-passed' if passed else 'telegram-phone-validation-failed',
        'reconciliation': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-operational-go-live-acceptance' if passed else 'telegram-validation-remediation',
    }


@router.get('/status')
def reconciliation_status() -> dict:
    return {
        'reconciliations': len(_reconciliation_store),
        'passed': sum(1 for item in _reconciliation_store.values() if item.get('validation_passed')),
        'failed': sum(1 for item in _reconciliation_store.values() if not item.get('validation_passed')),
        'external_calls_made': 0,
        'reconciliation_mode': 'phone-to-auron-to-phone-evidence-reconciliation',
    }


@router.get('/reconciliations')
def list_reconciliations() -> dict:
    items = sorted(_reconciliation_store.values(), key=lambda item: item['reconciled_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_operational_readiness_observability_v21_320 import command_center as v21_320_command_center

    html = v21_320_command_center().replace('v21.320', 'v21.321')
    return html.replace(
        'AURON TELEGRAM OPERATIONAL READINESS OBSERVABILITY COMMAND CENTER',
        'AURON TELEGRAM PHONE VALIDATION RECONCILIATION COMMAND CENTER',
    )
