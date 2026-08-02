from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_alert_delivery_commit_audit_v21_288 import _audit_store
from app.api.routes.auron_demo1_alert_delivery_state_commit_v21_287 import _commit_store
from app.api.routes.auron_demo1_completion_alert_delivery_boundary_v21_281 import _delivery_store

v21_289_router = APIRouter(prefix='/auron/demo1/v21.289', tags=['auron-demo1-alert-lifecycle-closure'])

_closure_store: dict[str, dict] = {}
_CLOSURE_VERSION = 'v21.289'


class AlertLifecycleClosureRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    archive: bool = True
    note: str | None = Field(default=None, max_length=500)


def reset_alert_lifecycle_closure_store() -> None:
    _closure_store.clear()


def _audit_for_commit(commit_id: str) -> dict | None:
    return next((item for item in _audit_store.values() if item['commit_id'] == commit_id), None)


def _chain_checks(commit: dict, audit: dict, delivery: dict) -> dict[str, bool]:
    return {
        'delivery_present': bool(delivery),
        'delivery_terminal': delivery.get('terminal') is True,
        'delivery_state_matches_commit': delivery.get('delivery_state') == commit.get('committed_delivery_state'),
        'delivery_commit_matches': delivery.get('delivery_state_commit_id') == commit.get('commit_id'),
        'audit_integrity_verified': audit.get('integrity_verified') is True,
        'audit_immutable': audit.get('immutable') is True,
        'audit_commit_matches': audit.get('commit_id') == commit.get('commit_id'),
        'audit_delivery_matches': audit.get('delivery_id') == commit.get('delivery_id'),
        'chain_identifiers_complete': all(
            commit.get(key)
            for key in ('commit_id', 'delivery_id', 'dispatch_id', 'retry_dispatch_id', 'retry_result_id')
        ),
    }


@v21_289_router.get('/status')
def lifecycle_closure_status() -> dict:
    archived = sum(1 for item in _closure_store.values() if item['archived'])
    return {
        'closed_alert_lifecycles': len(_closure_store),
        'archived_alert_lifecycles': archived,
        'closure_version': _CLOSURE_VERSION,
        'external_calls_made': 0,
        'terminal_execution_state_modified': False,
        'boundary_mode': 'internal-lifecycle-closure-only',
    }


@v21_289_router.post('/close/{commit_id}')
def close_alert_lifecycle(commit_id: str, payload: AlertLifecycleClosureRequest) -> dict:
    commit = _commit_store.get(commit_id)
    if commit is None:
        raise HTTPException(status_code=404, detail='Alert delivery commit not found')

    existing = next((item for item in _closure_store.values() if item['commit_id'] == commit_id), None)
    if existing is not None:
        return {'state': 'alert-lifecycle-already-closed', 'closure': existing, 'idempotent_replay': True, 'external_calls_made': 0, 'terminal_execution_state_modified': False}

    audit = _audit_for_commit(commit_id)
    if audit is None:
        raise HTTPException(status_code=409, detail='Immutable audit receipt required before lifecycle closure')
    delivery = _delivery_store.get(commit['delivery_id'])
    if delivery is None:
        raise HTTPException(status_code=409, detail='Alert delivery record not found for lifecycle closure')

    checks = _chain_checks(commit, audit, delivery)
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {'state': 'alert-lifecycle-closure-blocked', 'commit_id': commit_id, 'checks': checks, 'blockers': blockers, 'external_calls_made': 0, 'terminal_execution_state_modified': False, 'next_layer': 'alert-lifecycle-integrity-remediation'}

    closed_at = datetime.now(timezone.utc).isoformat()
    closure_id = str(uuid4())
    record = {
        'closure_id': closure_id, 'commit_id': commit_id, 'audit_id': audit['audit_id'],
        'delivery_id': commit['delivery_id'], 'dispatch_id': commit['dispatch_id'],
        'retry_dispatch_id': commit['retry_dispatch_id'], 'retry_result_id': commit['retry_result_id'],
        'final_delivery_state': commit['committed_delivery_state'], 'integrity_hash': audit['integrity_hash'],
        'chain_complete': True, 'lifecycle_closed': True, 'archived': payload.archive,
        'closed_by': payload.actor, 'closed_at': closed_at, 'closure_version': _CLOSURE_VERSION, 'note': payload.note,
    }
    _closure_store[closure_id] = record
    delivery['lifecycle_closed'] = True
    delivery['lifecycle_closure_id'] = closure_id
    delivery['lifecycle_closed_at'] = closed_at
    delivery['archived'] = payload.archive

    return {'state': 'alert-lifecycle-closed', 'closure': record, 'checks': checks, 'closure_store_mutations_made': 1, 'delivery_store_mutations_made': 1, 'external_calls_made': 0, 'business_mutations_made': 0, 'terminal_execution_state_modified': False, 'next_layer': 'next-auron-execution-framework-stage', 'reply': 'Der Alert-Lebenszyklus ist vollstaendig geprueft, geschlossen und intern archiviert.'}


@v21_289_router.get('/closures')
def list_lifecycle_closures() -> dict:
    items = sorted(_closure_store.values(), key=lambda item: item['closed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0, 'terminal_execution_state_modified': False}


@v21_289_router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_alert_delivery_commit_audit_v21_288 import command_center as v21_288_command_center
    html = v21_288_command_center()
    html = html.replace('v21.288', 'v21.289')
    html = html.replace('AURON ALERT DELIVERY COMMIT AUDIT COMMAND CENTER', 'AURON ALERT LIFECYCLE CLOSURE COMMAND CENTER')
    return html


from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import router as v21_290_router
from app.api.routes.auron_demo1_telegram_gateway_runtime_v21_291 import router as v21_291_router
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import router as v21_292_router
from app.api.routes.auron_demo1_telegram_conversation_router_v21_293 import router as v21_293_router
from app.api.routes.auron_demo1_telegram_controlled_send_adapter_v21_294 import router as v21_294_router
from app.api.routes.auron_demo1_telegram_provider_call_boundary_v21_295 import router as v21_295_router

router = APIRouter()
router.include_router(v21_289_router)
router.include_router(v21_290_router)
router.include_router(v21_291_router)
router.include_router(v21_292_router)
router.include_router(v21_293_router)
router.include_router(v21_294_router)
router.include_router(v21_295_router)
