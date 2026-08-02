from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_completion_alert_delivery_boundary_v21_281 import _delivery_store

router = APIRouter(prefix='/auron/demo1/v21.282', tags=['auron-demo1-controlled-alert-dispatch-adapter'])

_dispatch_store: dict[str, dict] = {}


class AlertDispatchRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    adapter_registered: bool = False
    runtime_available: bool = False
    recipient_verified: bool = False
    dry_run: bool = True


def reset_alert_dispatch_store() -> None:
    _dispatch_store.clear()


def _adapter_for(channel: str) -> str:
    lowered = channel.lower()
    if lowered in {'operator-console', 'console', 'internal'}:
        return 'internal-alert-adapter'
    if lowered in {'email', 'gmail'}:
        return 'email-alert-adapter'
    if lowered in {'slack', 'teams'}:
        return 'workspace-alert-adapter'
    return 'generic-notification-adapter'


@router.get('/status')
def dispatch_adapter_status() -> dict:
    prepared = len(_dispatch_store)
    return {
        'prepared_dispatches': prepared,
        'live_dispatch_enabled': False,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'adapter_mode': 'dry-run-only',
    }


@router.post('/dispatch/{delivery_id}')
def dispatch_alert(delivery_id: str, payload: AlertDispatchRequest) -> dict:
    delivery = _delivery_store.get(delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail='Alert delivery not found')
    if delivery['acknowledged']:
        raise HTTPException(status_code=409, detail='Acknowledged alert delivery cannot be dispatched')
    if payload.dry_run is not True:
        raise HTTPException(status_code=409, detail='Live alert dispatch is not enabled in v21.282')

    checks = {
        'adapter_registered': payload.adapter_registered,
        'runtime_available': payload.runtime_available,
        'recipient_verified': payload.recipient_verified,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'alert-dispatch-blocked',
            'delivery_id': delivery_id,
            'checks': checks,
            'blockers': blockers,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'alert-dispatch-remediation',
        }

    existing = next((item for item in _dispatch_store.values() if item['delivery_id'] == delivery_id), None)
    if existing is not None:
        return {
            'state': 'alert-dispatch-already-prepared',
            'dispatch': existing,
            'idempotent_replay': True,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'alert-dispatch-result-verification',
        }

    dispatch_id = str(uuid4())
    record = {
        'dispatch_id': dispatch_id,
        'delivery_id': delivery_id,
        'adapter': _adapter_for(delivery['channel']),
        'channel': delivery['channel'],
        'recipient': delivery['recipient'],
        'severity': delivery['severity'],
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'dispatch_state': 'dry-run-prepared',
        'dry_run': True,
        'notification_dispatched': False,
        'external_calls_made': 0,
    }
    _dispatch_store[dispatch_id] = record
    return {
        'state': 'alert-dispatch-prepared',
        'dispatch': record,
        'checks': checks,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'alert_dispatch_store_mutations_made': 1,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-dispatch-result-verification',
        'reply': 'Alert Dispatch wurde als kontrollierter Dry-Run vorbereitet. Es wurde keine externe Benachrichtigung versendet.',
    }


@router.get('/dispatches')
def list_dispatches() -> dict:
    items = sorted(_dispatch_store.values(), key=lambda item: item['prepared_at'])
    return {
        'count': len(items),
        'items': items,
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_completion_alert_delivery_boundary_v21_281 import command_center as v21_281_command_center

    html = v21_281_command_center()
    html = html.replace('v21.281', 'v21.282')
    html = html.replace(
        'AURON COMPLETION ALERT DELIVERY BOUNDARY COMMAND CENTER',
        'AURON CONTROLLED ALERT DISPATCH ADAPTER COMMAND CENTER',
    )
    return html
