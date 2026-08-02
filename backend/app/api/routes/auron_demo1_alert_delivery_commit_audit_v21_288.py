from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_alert_delivery_state_commit_v21_287 import _commit_store

router = APIRouter(prefix='/auron/demo1/v21.288', tags=['auron-demo1-alert-delivery-commit-audit'])

_audit_store: dict[str, dict] = {}
_AUDIT_VERSION = 'v21.288'


class DeliveryCommitAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


def reset_delivery_commit_audit_store() -> None:
    _audit_store.clear()


def _canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return sha256(raw.encode('utf-8')).hexdigest()


def _integrity_payload(commit: dict) -> dict:
    return {
        'commit_id': commit['commit_id'],
        'delivery_id': commit['delivery_id'],
        'retry_result_id': commit['retry_result_id'],
        'retry_dispatch_id': commit['retry_dispatch_id'],
        'dispatch_id': commit['dispatch_id'],
        'attempt': commit['attempt'],
        'provider_status': commit['provider_status'],
        'provider_receipt_id': commit.get('provider_receipt_id'),
        'previous_delivery_state': commit.get('previous_delivery_state'),
        'committed_delivery_state': commit['committed_delivery_state'],
        'committed_by': commit['committed_by'],
        'committed_at': commit['committed_at'],
        'note': commit.get('note'),
        'audit_version': _AUDIT_VERSION,
    }


@router.get('/status')
def delivery_commit_audit_status() -> dict:
    return {
        'audit_receipts': len(_audit_store),
        'audit_version': _AUDIT_VERSION,
        'immutable_receipts': True,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'integrity-audit-only',
    }


@router.post('/audit/{commit_id}')
def audit_delivery_commit(commit_id: str, payload: DeliveryCommitAuditRequest) -> dict:
    commit = _commit_store.get(commit_id)
    if commit is None:
        raise HTTPException(status_code=404, detail='Alert delivery commit not found')

    existing = next((item for item in _audit_store.values() if item['commit_id'] == commit_id), None)
    if existing is not None:
        return {
            'state': 'alert-delivery-commit-already-audited',
            'receipt': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
            'terminal_execution_state_modified': False,
        }

    integrity_payload = _integrity_payload(commit)
    integrity_hash = _canonical_hash(integrity_payload)
    receipt_id = str(uuid4())
    record = {
        'audit_id': receipt_id,
        'commit_id': commit_id,
        'delivery_id': commit['delivery_id'],
        'dispatch_id': commit['dispatch_id'],
        'retry_dispatch_id': commit['retry_dispatch_id'],
        'retry_result_id': commit['retry_result_id'],
        'committed_delivery_state': commit['committed_delivery_state'],
        'integrity_hash': integrity_hash,
        'hash_algorithm': 'sha256',
        'audited_by': payload.actor,
        'audited_at': datetime.now(timezone.utc).isoformat(),
        'audit_version': _AUDIT_VERSION,
        'immutable': True,
        'integrity_verified': True,
        'note': payload.note,
    }
    _audit_store[receipt_id] = record
    return {
        'state': 'alert-delivery-commit-audited',
        'receipt': record,
        'audit_store_mutations_made': 1,
        'external_calls_made': 0,
        'business_mutations_made': 0,
        'terminal_execution_state_modified': False,
        'next_layer': 'alert-lifecycle-closure',
        'reply': 'Der Alert-Delivery-Commit wurde geprueft und mit einem unveraenderbaren Integrity Receipt abgeschlossen.',
    }


@router.get('/receipt/{audit_id}')
def get_audit_receipt(audit_id: str) -> dict:
    receipt = _audit_store.get(audit_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail='Alert delivery audit receipt not found')
    return {
        'receipt': receipt,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/receipts')
def list_audit_receipts() -> dict:
    items = sorted(_audit_store.values(), key=lambda item: item['audited_at'])
    return {
        'count': len(items),
        'items': items,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_alert_delivery_state_commit_v21_287 import command_center as v21_287_command_center

    html = v21_287_command_center()
    html = html.replace('v21.287', 'v21.288')
    html = html.replace(
        'AURON ALERT DELIVERY STATE COMMIT COMMAND CENTER',
        'AURON ALERT DELIVERY COMMIT AUDIT COMMAND CENTER',
    )
    return html
