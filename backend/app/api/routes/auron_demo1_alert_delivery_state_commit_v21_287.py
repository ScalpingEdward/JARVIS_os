from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_alert_retry_result_verification_v21_286 import _retry_result_store
from app.api.routes.auron_demo1_completion_alert_delivery_boundary_v21_281 import _delivery_store

router = APIRouter(prefix='/auron/demo1/v21.287', tags=['auron-demo1-alert-delivery-state-commit'])

_commit_store: dict[str, dict] = {}


class DeliveryStateCommitRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


def reset_delivery_state_commit_store() -> None:
    _commit_store.clear()


def _terminal_result_for_delivery(delivery_id: str) -> dict | None:
    items = [item for item in _retry_result_store.values() if item['delivery_id'] == delivery_id and item['terminal']]
    if not items:
        return None
    return max(items, key=lambda item: item['verified_at'])


@router.get('/status')
def delivery_state_commit_status() -> dict:
    return {
        'committed_delivery_states': len(_commit_store),
        'external_calls_made': 0,
        'notifications_dispatched_by_v21_287': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'internal-alert-state-commit-only',
    }


@router.post('/commit/{delivery_id}')
def commit_delivery_state(delivery_id: str, payload: DeliveryStateCommitRequest) -> dict:
    delivery = _delivery_store.get(delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail='Alert delivery not found')

    existing = next((item for item in _commit_store.values() if item['delivery_id'] == delivery_id), None)
    if existing is not None:
        return {
            'state': 'alert-delivery-state-already-committed',
            'commit': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
            'terminal_execution_state_modified': False,
        }

    result = _terminal_result_for_delivery(delivery_id)
    if result is None:
        raise HTTPException(status_code=409, detail='Terminal retry result required before delivery-state commit')

    committed_state = result['delivery_state']
    committed_at = datetime.now(timezone.utc).isoformat()
    commit_id = str(uuid4())
    record = {
        'commit_id': commit_id,
        'delivery_id': delivery_id,
        'retry_result_id': result['result_id'],
        'retry_dispatch_id': result['retry_dispatch_id'],
        'dispatch_id': result['dispatch_id'],
        'attempt': result['attempt'],
        'provider_status': result['provider_status'],
        'provider_receipt_id': result.get('provider_receipt_id'),
        'previous_delivery_state': delivery.get('delivery_state'),
        'committed_delivery_state': committed_state,
        'committed_by': payload.actor,
        'committed_at': committed_at,
        'note': payload.note,
    }
    _commit_store[commit_id] = record
    delivery['delivery_state'] = committed_state
    delivery['terminal'] = True
    delivery['delivery_state_committed_at'] = committed_at
    delivery['delivery_state_commit_id'] = commit_id

    return {
        'state': 'alert-delivery-state-committed',
        'commit': record,
        'delivery_store_mutations_made': 1,
        'commit_store_mutations_made': 1,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-delivery-commit-audit',
        'reply': 'Der terminale Provider-Ausgang wurde intern in den Alert-Delivery-Status uebernommen.',
    }


@router.get('/commits')
def list_delivery_state_commits() -> dict:
    items = sorted(_commit_store.values(), key=lambda item: item['committed_at'])
    return {
        'count': len(items),
        'items': items,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_alert_retry_result_verification_v21_286 import command_center as v21_286_command_center

    html = v21_286_command_center()
    html = html.replace('v21.286', 'v21.287')
    html = html.replace(
        'AURON ALERT RETRY RESULT VERIFICATION COMMAND CENTER',
        'AURON ALERT DELIVERY STATE COMMIT COMMAND CENTER',
    )
    return html
