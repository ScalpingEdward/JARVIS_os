from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_alert_dispatch_retry_controller_v21_284 import _retry_store
from app.api.routes.auron_demo1_controlled_alert_dispatch_adapter_v21_282 import _dispatch_store

router = APIRouter(prefix='/auron/demo1/v21.285', tags=['auron-demo1-controlled-alert-retry-dispatch'])

_retry_dispatch_store: dict[str, dict] = {}


class ControlledRetryDispatchRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    adapter_registered: bool = False
    runtime_available: bool = False
    recipient_verified: bool = False
    force_eligible: bool = False
    dry_run: bool = True


def reset_retry_dispatch_store() -> None:
    _retry_dispatch_store.clear()


def _is_eligible(retry: dict, force_eligible: bool) -> bool:
    if force_eligible:
        return True
    return datetime.fromisoformat(retry['eligible_at']) <= datetime.now(timezone.utc)


@router.get('/status')
def retry_dispatch_status() -> dict:
    return {
        'prepared_retry_dispatches': len(_retry_dispatch_store),
        'live_retry_dispatch_enabled': False,
        'provider_call_performed': False,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'bounded-dry-run-only',
    }


@router.post('/dispatch/{retry_id}')
def dispatch_retry(retry_id: str, payload: ControlledRetryDispatchRequest) -> dict:
    retry = _retry_store.get(retry_id)
    if retry is None:
        raise HTTPException(status_code=404, detail='Scheduled alert retry not found')

    existing = next((item for item in _retry_dispatch_store.values() if item['retry_id'] == retry_id), None)
    if existing is not None:
        return {
            'state': 'alert-retry-dispatch-already-prepared',
            'retry_dispatch': existing,
            'idempotent_replay': True,
            'provider_call_performed': False,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'alert-retry-result-verification',
        }

    if retry['retry_state'] != 'scheduled':
        raise HTTPException(status_code=409, detail='Alert retry is not in scheduled state')
    if payload.dry_run is not True:
        raise HTTPException(status_code=409, detail='Live alert retry dispatch is not enabled in v21.285')
    if not _is_eligible(retry, payload.force_eligible):
        raise HTTPException(status_code=409, detail='Alert retry is not eligible yet')

    dispatch = _dispatch_store.get(retry['dispatch_id'])
    if dispatch is None:
        raise HTTPException(status_code=409, detail='Original alert dispatch not found')

    checks = {
        'adapter_registered': payload.adapter_registered,
        'runtime_available': payload.runtime_available,
        'recipient_verified': payload.recipient_verified,
        'within_attempt_budget': retry['attempt'] <= retry['max_attempts'],
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'alert-retry-dispatch-blocked',
            'retry_id': retry_id,
            'checks': checks,
            'blockers': blockers,
            'provider_call_performed': False,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'alert-retry-dispatch-remediation',
        }

    retry_dispatch_id = str(uuid4())
    record = {
        'retry_dispatch_id': retry_dispatch_id,
        'retry_id': retry_id,
        'dispatch_id': retry['dispatch_id'],
        'delivery_id': retry['delivery_id'],
        'attempt': retry['attempt'],
        'max_attempts': retry['max_attempts'],
        'adapter': dispatch['adapter'],
        'channel': dispatch['channel'],
        'recipient': dispatch['recipient'],
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'retry_dispatch_state': 'dry-run-prepared',
        'dry_run': True,
        'provider_call_performed': False,
        'notification_dispatched': False,
        'external_calls_made': 0,
    }
    _retry_dispatch_store[retry_dispatch_id] = record
    retry['retry_state'] = 'dispatch-prepared'
    retry['dispatch_prepared_at'] = record['prepared_at']

    return {
        'state': 'alert-retry-dispatch-prepared',
        'retry_dispatch': record,
        'checks': checks,
        'retry_store_mutations_made': 1,
        'retry_dispatch_store_mutations_made': 1,
        'provider_call_performed': False,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-retry-result-verification',
        'reply': 'Ein begrenzter Alert-Retry wurde als Dry-Run vorbereitet. Der Provider wurde nicht erneut aufgerufen.',
    }


@router.get('/retry-dispatches')
def list_retry_dispatches() -> dict:
    items = sorted(_retry_dispatch_store.values(), key=lambda item: item['prepared_at'])
    return {
        'count': len(items),
        'items': items,
        'provider_call_performed': False,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_alert_dispatch_retry_controller_v21_284 import command_center as v21_284_command_center

    html = v21_284_command_center()
    html = html.replace('v21.284', 'v21.285')
    html = html.replace(
        'AURON ALERT DISPATCH RETRY CONTROLLER COMMAND CENTER',
        'AURON CONTROLLED ALERT RETRY DISPATCH COMMAND CENTER',
    )
    return html
