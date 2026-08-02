from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_controlled_alert_retry_dispatch_v21_285 import _retry_dispatch_store

router = APIRouter(prefix='/auron/demo1/v21.286', tags=['auron-demo1-alert-retry-result-verification'])

_retry_result_store: dict[str, dict] = {}


class RetryResultVerificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    provider_status: str = Field(pattern='^(accepted|delivered|temporary-failure|permanent-failure)$')
    provider_receipt_id: str | None = Field(default=None, max_length=200)
    provider_message: str | None = Field(default=None, max_length=500)


def reset_retry_result_store() -> None:
    _retry_result_store.clear()


def _classify(status: str, attempt: int, max_attempts: int) -> dict:
    if status == 'delivered':
        return {'verified': True, 'retryable': False, 'terminal': True, 'delivery_state': 'verified-delivered'}
    if status == 'accepted':
        return {'verified': False, 'retryable': True, 'terminal': False, 'delivery_state': 'provider-accepted-pending'}
    if status == 'temporary-failure':
        exhausted = attempt >= max_attempts
        return {
            'verified': False,
            'retryable': not exhausted,
            'terminal': exhausted,
            'delivery_state': 'retry-exhausted' if exhausted else 'retryable-failure',
        }
    return {'verified': False, 'retryable': False, 'terminal': True, 'delivery_state': 'permanent-failure'}


@router.get('/status')
def retry_result_status() -> dict:
    return {
        'verified_retry_results': len(_retry_result_store),
        'provider_call_performed_by_v21_286': False,
        'notification_dispatched_by_v21_286': False,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'provider-receipt-correlation-only',
    }


@router.post('/verify/{retry_dispatch_id}')
def verify_retry_result(retry_dispatch_id: str, payload: RetryResultVerificationRequest) -> dict:
    retry_dispatch = _retry_dispatch_store.get(retry_dispatch_id)
    if retry_dispatch is None:
        raise HTTPException(status_code=404, detail='Alert retry dispatch not found')

    existing = next(
        (item for item in _retry_result_store.values() if item['retry_dispatch_id'] == retry_dispatch_id),
        None,
    )
    if existing is not None:
        return {
            'state': 'alert-retry-result-already-verified',
            'result': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
            'terminal_execution_state_modified': False,
        }

    outcome = _classify(
        payload.provider_status,
        retry_dispatch['attempt'],
        retry_dispatch['max_attempts'],
    )
    result_id = str(uuid4())
    record = {
        'result_id': result_id,
        'retry_dispatch_id': retry_dispatch_id,
        'retry_id': retry_dispatch['retry_id'],
        'dispatch_id': retry_dispatch['dispatch_id'],
        'delivery_id': retry_dispatch['delivery_id'],
        'attempt': retry_dispatch['attempt'],
        'max_attempts': retry_dispatch['max_attempts'],
        'adapter': retry_dispatch['adapter'],
        'channel': retry_dispatch['channel'],
        'recipient': retry_dispatch['recipient'],
        'provider_status': payload.provider_status,
        'provider_receipt_id': payload.provider_receipt_id,
        'provider_message': payload.provider_message,
        'verified_by': payload.actor,
        'verified_at': datetime.now(timezone.utc).isoformat(),
        **outcome,
        'provider_call_performed_by_v21_286': False,
        'notification_dispatched_by_v21_286': False,
        'external_calls_made': 0,
    }
    _retry_result_store[result_id] = record
    retry_dispatch['retry_dispatch_state'] = 'result-verified'
    retry_dispatch['result_verified_at'] = record['verified_at']

    return {
        'state': 'alert-retry-result-verified',
        'result': record,
        'retry_result_store_mutations_made': 1,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-delivery-state-commit' if outcome['terminal'] else 'alert-dispatch-retry-controller',
    }


@router.get('/results')
def list_retry_results() -> dict:
    items = sorted(_retry_result_store.values(), key=lambda item: item['verified_at'])
    return {
        'count': len(items),
        'items': items,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_controlled_alert_retry_dispatch_v21_285 import command_center as v21_285_command_center

    html = v21_285_command_center()
    html = html.replace('v21.285', 'v21.286')
    html = html.replace(
        'AURON CONTROLLED ALERT RETRY DISPATCH COMMAND CENTER',
        'AURON ALERT RETRY RESULT VERIFICATION COMMAND CENTER',
    )
    return html
