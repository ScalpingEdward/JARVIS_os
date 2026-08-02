from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_alert_dispatch_result_verification_v21_283 import _result_store
from app.api.routes.auron_demo1_controlled_alert_dispatch_adapter_v21_282 import _dispatch_store

router = APIRouter(prefix='/auron/demo1/v21.284', tags=['auron-demo1-alert-dispatch-retry-controller'])

_MAX_ATTEMPTS = 3
_retry_store: dict[str, dict] = {}


class RetryScheduleRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    delay_seconds: int = Field(default=30, ge=1, le=3600)


def reset_retry_store() -> None:
    _retry_store.clear()


def _latest_result(dispatch_id: str) -> dict | None:
    items = [item for item in _result_store.values() if item['dispatch_id'] == dispatch_id]
    if not items:
        return None
    return max(items, key=lambda item: (item['attempt'], item['verified_at']))


@router.get('/status')
def retry_controller_status() -> dict:
    scheduled = [item for item in _retry_store.values() if item['retry_state'] == 'scheduled']
    return {
        'retry_records': len(_retry_store),
        'scheduled_retries': len(scheduled),
        'max_attempts': _MAX_ATTEMPTS,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
        'controller_mode': 'schedule-only',
    }


@router.post('/schedule/{dispatch_id}')
def schedule_retry(dispatch_id: str, payload: RetryScheduleRequest) -> dict:
    dispatch = _dispatch_store.get(dispatch_id)
    if dispatch is None:
        raise HTTPException(status_code=404, detail='Alert dispatch not found')
    result = _latest_result(dispatch_id)
    if result is None:
        raise HTTPException(status_code=409, detail='Dispatch result must be verified before retry scheduling')
    if result['terminal'] or not result['retryable']:
        raise HTTPException(status_code=409, detail='Dispatch result is not retryable')

    next_attempt = result['attempt'] + 1
    if next_attempt > _MAX_ATTEMPTS:
        raise HTTPException(status_code=409, detail='Retry attempt budget exhausted')

    existing = next(
        (
            item
            for item in _retry_store.values()
            if item['dispatch_id'] == dispatch_id and item['attempt'] == next_attempt
        ),
        None,
    )
    if existing is not None:
        return {
            'state': 'alert-retry-already-scheduled',
            'retry': existing,
            'idempotent_replay': True,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'terminal_execution_state_modified': False,
        }

    now = datetime.now(timezone.utc)
    retry_id = str(uuid4())
    record = {
        'retry_id': retry_id,
        'dispatch_id': dispatch_id,
        'delivery_id': dispatch['delivery_id'],
        'attempt': next_attempt,
        'max_attempts': _MAX_ATTEMPTS,
        'attempts_remaining_after_schedule': _MAX_ATTEMPTS - next_attempt,
        'scheduled_by': payload.actor,
        'scheduled_at': now.isoformat(),
        'eligible_at': (now + timedelta(seconds=payload.delay_seconds)).isoformat(),
        'delay_seconds': payload.delay_seconds,
        'retry_state': 'scheduled',
        'provider_call_performed': False,
        'notification_dispatched': False,
        'external_calls_made': 0,
    }
    _retry_store[retry_id] = record
    return {
        'state': 'alert-retry-scheduled',
        'retry': record,
        'retry_store_mutations_made': 1,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'next_layer': 'controlled-alert-retry-dispatch',
        'reply': 'Alert-Retry wurde innerhalb des Attempt-Budgets geplant. Es wurde noch kein Provider erneut aufgerufen.',
    }


@router.get('/retries')
def list_retries() -> dict:
    items = sorted(_retry_store.values(), key=lambda item: item['scheduled_at'])
    return {
        'count': len(items),
        'items': items,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_alert_dispatch_result_verification_v21_283 import command_center as v21_283_command_center

    html = v21_283_command_center()
    html = html.replace('v21.283', 'v21.284')
    html = html.replace(
        'AURON ALERT DISPATCH RESULT VERIFICATION COMMAND CENTER',
        'AURON ALERT DISPATCH RETRY CONTROLLER COMMAND CENTER',
    )
    return html
