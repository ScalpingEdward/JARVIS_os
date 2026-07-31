from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_completion_alert_policy_v21_280 import _evaluate
from app.api.routes.auron_demo1_completion_observability_v21_279 import _entries

router = APIRouter(prefix='/auron/demo1/v21.281', tags=['auron-demo1-completion-alert-delivery-boundary'])

_delivery_store: dict[str, dict] = {}
_dedupe_index: dict[str, str] = {}


class AlertDeliveryPrepareRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    channel: str = Field(default='operator-console', min_length=1, max_length=120)
    recipient: str = Field(default='operator', min_length=1, max_length=160)


class AlertAcknowledgementRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


def reset_alert_delivery_store() -> None:
    _delivery_store.clear()
    _dedupe_index.clear()


def _canonical_digest(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(raw.encode('utf-8')).hexdigest()


def _delivery_fingerprint(evaluation: dict, channel: str, recipient: str) -> str:
    payload = {
        'severity': evaluation.get('severity'),
        'reasons': evaluation.get('reasons') or [],
        'health': evaluation.get('health') or {},
        'channel': channel,
        'recipient': recipient,
    }
    return _canonical_digest(payload)


def _delivery_view(record: dict) -> dict:
    return {
        'delivery_id': record['delivery_id'],
        'severity': record['severity'],
        'reasons': record['reasons'],
        'channel': record['channel'],
        'recipient': record['recipient'],
        'delivery_state': record['delivery_state'],
        'prepared_at': record['prepared_at'],
        'acknowledged': record['acknowledged'],
        'acknowledged_at': record.get('acknowledged_at'),
        'acknowledged_by': record.get('acknowledged_by'),
        'dedupe_fingerprint': record['dedupe_fingerprint'],
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/status')
def alert_delivery_status() -> dict:
    active = [record for record in _delivery_store.values() if not record['acknowledged']]
    acknowledged = [record for record in _delivery_store.values() if record['acknowledged']]
    return {
        'prepared_deliveries': len(_delivery_store),
        'active_unacknowledged': len(active),
        'acknowledged': len(acknowledged),
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'prepare-dedupe-acknowledge',
    }


@router.post('/prepare')
def prepare_alert_delivery(payload: AlertDeliveryPrepareRequest) -> dict:
    evaluation = _evaluate(_entries())
    if evaluation.get('severity') == 'ok' or not evaluation.get('signal_active'):
        return {
            'state': 'no-alert-delivery-required',
            'severity': evaluation.get('severity'),
            'delivery_prepared': False,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'completion-alert-policy-monitoring',
        }

    fingerprint = _delivery_fingerprint(evaluation, payload.channel, payload.recipient)
    existing_id = _dedupe_index.get(fingerprint)
    if existing_id is not None:
        existing = _delivery_store[existing_id]
        return {
            'state': 'alert-delivery-deduplicated',
            'delivery_prepared': True,
            'deduplicated': True,
            'delivery': _delivery_view(existing),
            'notification_dispatched': False,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'alert-delivery-acknowledgement' if not existing['acknowledged'] else 'alert-policy-re-evaluation',
        }

    delivery_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'delivery_id': delivery_id,
        'severity': evaluation['severity'],
        'reasons': list(evaluation.get('reasons') or []),
        'health': evaluation.get('health') or {},
        'channel': payload.channel,
        'recipient': payload.recipient,
        'prepared_by': payload.actor,
        'prepared_at': now,
        'delivery_state': 'prepared-not-dispatched',
        'dedupe_fingerprint': fingerprint,
        'acknowledged': False,
        'acknowledged_at': None,
        'acknowledged_by': None,
        'acknowledgement_note': None,
    }
    _delivery_store[delivery_id] = record
    _dedupe_index[fingerprint] = delivery_id
    return {
        'state': 'alert-delivery-prepared',
        'delivery_prepared': True,
        'deduplicated': False,
        'delivery': _delivery_view(record),
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'alert_store_mutations_made': 1,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-delivery-acknowledgement',
        'reply': 'Alert Delivery wurde vorbereitet und dedupliziert. Es wurde noch keine externe Benachrichtigung versendet.',
    }


@router.post('/acknowledge/{delivery_id}')
def acknowledge_alert_delivery(delivery_id: str, payload: AlertAcknowledgementRequest) -> dict:
    record = _delivery_store.get(delivery_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Alert delivery not found')
    if record['acknowledged']:
        return {
            'state': 'alert-delivery-already-acknowledged',
            'delivery': _delivery_view(record),
            'idempotent_replay': True,
            'notification_dispatched': False,
            'external_calls_made': 0,
            'business_mutations_made': 0,
            'terminal_execution_state_modified': False,
            'next_layer': 'alert-policy-re-evaluation',
        }

    record['acknowledged'] = True
    record['acknowledged_at'] = datetime.now(timezone.utc).isoformat()
    record['acknowledged_by'] = payload.actor
    record['acknowledgement_note'] = payload.note
    record['delivery_state'] = 'acknowledged-not-dispatched'
    return {
        'state': 'alert-delivery-acknowledged',
        'delivery': _delivery_view(record),
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'alert_store_mutations_made': 1,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-policy-re-evaluation',
    }


@router.get('/deliveries')
def list_alert_deliveries(
    acknowledged: str = Query(default='all', pattern='^(all|yes|no)$'),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    items: list[dict] = []
    for record in _delivery_store.values():
        if acknowledged == 'yes' and not record['acknowledged']:
            continue
        if acknowledged == 'no' and record['acknowledged']:
            continue
        items.append(_delivery_view(record))
    items.sort(key=lambda item: item['prepared_at'])
    total = len(items)
    return {
        'count': min(total, limit),
        'total_matching': total,
        'items': items[:limit],
        'notification_dispatched': False,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_completion_alert_policy_v21_280 import command_center as v21_280_command_center

    html = v21_280_command_center()
    html = html.replace('v21.280', 'v21.281')
    html = html.replace(
        'AURON COMPLETION ALERT POLICY COMMAND CENTER',
        'AURON COMPLETION ALERT DELIVERY BOUNDARY COMMAND CENTER',
    )
    return html
