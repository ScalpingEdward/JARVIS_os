from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_analytics_health_supervisor_v21_327 import (
    _anomaly_store,
    _health_snapshot_store,
    _metrics,
)
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store

router = APIRouter(prefix='/auron/demo1/v21.328', tags=['auron-demo1-telegram-runtime-health-remediation'])

_remediation_store: dict[str, dict] = {}
_ACK_PHRASE = 'ACKNOWLEDGE AURON TELEGRAM RUNTIME ANOMALY'
_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM CONTINUOUS SERVICE'


class TelegramRuntimeAnomalyAcknowledgeRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    anomaly_id: str = Field(min_length=1, max_length=160)
    acknowledgement_phrase: str = Field(min_length=1, max_length=220)
    remediation_plan: str = Field(min_length=1, max_length=1000)


class TelegramRuntimeServiceRestoreRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    anomaly_id: str = Field(min_length=1, max_length=160)
    restore_phrase: str = Field(min_length=1, max_length=220)
    evidence_id: str = Field(min_length=1, max_length=200)


def reset_telegram_runtime_health_remediation_store() -> None:
    _remediation_store.clear()


def _anomaly(anomaly_id: str) -> dict:
    item = _anomaly_store.get(anomaly_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Telegram runtime-health anomaly not found')
    return item


@router.post('/acknowledge')
def acknowledge_runtime_anomaly(payload: TelegramRuntimeAnomalyAcknowledgeRequest) -> dict:
    if payload.acknowledgement_phrase != _ACK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit runtime-anomaly acknowledgement required')
    existing = _remediation_store.get(payload.anomaly_id)
    if existing is not None:
        return {'state': 'telegram-runtime-anomaly-already-acknowledged', 'remediation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    anomaly = _anomaly(payload.anomaly_id)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'remediation_id': str(uuid4()),
        'anomaly_id': payload.anomaly_id,
        'health_snapshot_id': anomaly['health_snapshot_id'],
        'telegram_chat_id': anomaly['telegram_chat_id'],
        'severity': anomaly['severity'],
        'blockers': list(anomaly.get('blockers', [])),
        'remediation_plan': payload.remediation_plan,
        'remediation_state': 'acknowledged-awaiting-health-restoration',
        'acknowledged_by': payload.actor,
        'acknowledged_at': now,
        'restored_at': None,
        'external_calls_made': 0,
    }
    _remediation_store[payload.anomaly_id] = record
    anomaly['acknowledged'] = True
    anomaly['acknowledged_by'] = payload.actor
    anomaly['acknowledged_at'] = now
    return {'state': 'telegram-runtime-anomaly-acknowledged', 'remediation': record, 'external_calls_made': 0}


@router.post('/restore')
def restore_runtime_service(payload: TelegramRuntimeServiceRestoreRequest) -> dict:
    if payload.restore_phrase != _RESTORE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit controlled service-restoration approval required')
    anomaly = _anomaly(payload.anomaly_id)
    remediation = _remediation_store.get(payload.anomaly_id)
    if remediation is None:
        raise HTTPException(status_code=409, detail='Runtime anomaly must be acknowledged before restoration')
    if remediation.get('remediation_state') == 'restored':
        return {'state': 'telegram-runtime-service-already-restored', 'remediation': remediation, 'idempotent_replay': True, 'external_calls_made': 0}

    chat_id = anomaly['telegram_chat_id']
    latest = _health_snapshot_store.get(chat_id)
    metrics = _metrics(chat_id)
    checks = {
        'latest_snapshot_present': latest is not None,
        'latest_health_not_critical': bool(latest and latest.get('health_state') in {'healthy', 'degraded'}),
        'no_dead_letters': metrics['dead_letters'] == 0,
        'no_failed_worker_calls': metrics['failed_worker_calls'] == 0,
        'no_active_sequences': metrics['active_sequences'] == 0,
        'evidence_present': bool(payload.evidence_id),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram runtime service restoration blocked', 'blockers': blockers})

    go_live = _go_live_store.get(chat_id)
    if go_live is None:
        raise HTTPException(status_code=404, detail='Telegram go-live acceptance not found for this chat')
    now = datetime.now(timezone.utc).isoformat()
    circuit = _circuit_store.setdefault(chat_id, {'telegram_chat_id': chat_id})
    circuit.update(state='closed', consecutive_failures=0, reset_at=now, reset_by=payload.actor)
    go_live.update(continuous_mode_active=True, go_live_state='restored-after-health-remediation', restored_at=now)
    remediation.update(
        remediation_state='restored',
        restoration_checks=checks,
        restoration_evidence_id=payload.evidence_id,
        restored_by=payload.actor,
        restored_at=now,
    )
    anomaly['resolved'] = True
    anomaly['resolved_at'] = now
    return {'state': 'telegram-runtime-service-restored', 'remediation': remediation, 'external_calls_made': 0}


@router.get('/status')
def remediation_status() -> dict:
    items = list(_remediation_store.values())
    return {
        'remediations': len(items),
        'awaiting_restoration': sum(1 for item in items if item.get('remediation_state') == 'acknowledged-awaiting-health-restoration'),
        'restored': sum(1 for item in items if item.get('remediation_state') == 'restored'),
        'external_calls_made': 0,
        'mode': 'operator-acknowledged-evidence-gated-controlled-restoration',
    }


@router.get('/remediations')
def list_remediations() -> dict:
    items = sorted(_remediation_store.values(), key=lambda item: item['acknowledged_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_operational_analytics_health_supervisor_v21_327 import command_center as v21_327_command_center
    return v21_327_command_center().replace('v21.327', 'v21.328').replace(
        'AURON TELEGRAM OPERATIONAL ANALYTICS HEALTH SUPERVISOR COMMAND CENTER',
        'AURON TELEGRAM RUNTIME HEALTH REMEDIATION COMMAND CENTER',
    )
