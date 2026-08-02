from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_controlled_alert_dispatch_adapter_v21_282 import _dispatch_store

router = APIRouter(prefix='/auron/demo1/v21.283', tags=['auron-demo1-alert-dispatch-result-verification'])

_result_store: dict[str, dict] = {}


class DispatchResultVerificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    provider_status: str = Field(pattern='^(accepted|delivered|temporary-failure|permanent-failure)$')
    provider_receipt_id: str | None = Field(default=None, max_length=200)
    provider_message: str | None = Field(default=None, max_length=500)
    attempt: int = Field(default=1, ge=1, le=20)


def reset_dispatch_result_store() -> None:
    _result_store.clear()


def _classification(status: str, attempt: int) -> dict:
    if status == 'delivered':
        return {'verified': True, 'retryable': False, 'terminal': True, 'delivery_state': 'verified-delivered'}
    if status == 'accepted':
        return {'verified': False, 'retryable': True, 'terminal': False, 'delivery_state': 'provider-accepted-pending'}
    if status == 'temporary-failure':
        exhausted = attempt >= 3
        return {
            'verified': False,
            'retryable': not exhausted,
            'terminal': exhausted,
            'delivery_state': 'retry-exhausted' if exhausted else 'retry-scheduled',
        }
    return {'verified': False, 'retryable': False, 'terminal': True, 'delivery_state': 'permanent-failure'}


@router.get('/status')
def verification_status() -> dict:
    return {
        'verified_results': len(_result_store),
        'notification_dispatched_by_v21_283': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'provider-receipt-verification-only',
    }


@router.post('/verify/{dispatch_id}')
def verify_dispatch_result(dispatch_id: str, payload: DispatchResultVerificationRequest) -> dict:
    dispatch = _dispatch_store.get(dispatch_id)
    if dispatch is None:
        raise HTTPException(status_code=404, detail='Alert dispatch not found')

    existing = next((item for item in _result_store.values() if item['dispatch_id'] == dispatch_id and item['attempt'] == payload.attempt), None)
    if existing is not None:
        return {
            'state': 'dispatch-result-already-verified',
            'result': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'terminal_execution_state_modified': False,
        }

    outcome = _classification(payload.provider_status, payload.attempt)
    result_id = str(uuid4())
    record = {
        'result_id': result_id,
        'dispatch_id': dispatch_id,
        'delivery_id': dispatch['delivery_id'],
        'adapter': dispatch['adapter'],
        'channel': dispatch['channel'],
        'recipient': dispatch['recipient'],
        'provider_status': payload.provider_status,
        'provider_receipt_id': payload.provider_receipt_id,
        'provider_message': payload.provider_message,
        'attempt': payload.attempt,
        'verified_by': payload.actor,
        'verified_at': datetime.now(timezone.utc).isoformat(),
        **outcome,
        'notification_dispatched_by_v21_283': False,
        'external_calls_made': 0,
    }
    _result_store[result_id] = record
    return {
        'state': 'dispatch-result-verified',
        'result': record,
        'result_store_mutations_made': 1,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-delivery-state-commit' if outcome['terminal'] else 'alert-dispatch-retry-controller',
    }


@router.get('/results')
def list_results() -> dict:
    items = sorted(_result_store.values(), key=lambda item: item['verified_at'])
    return {
        'count': len(items),
        'items': items,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_controlled_alert_dispatch_adapter_v21_282 import command_center as v21_282_command_center

    html = v21_282_command_center()
    html = html.replace('v21.282', 'v21.283')
    html = html.replace(
        'AURON CONTROLLED ALERT DISPATCH ADAPTER COMMAND CENTER',
        'AURON ALERT DISPATCH RESULT VERIFICATION COMMAND CENTER',
    )
    return html
