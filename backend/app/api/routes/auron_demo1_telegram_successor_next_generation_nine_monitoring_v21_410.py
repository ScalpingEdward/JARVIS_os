from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_stabilization_v21_409 import (
    _certification_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.410',
    tags=['auron-demo1-telegram-successor-next-generation-nine-monitoring'],
)

_monitoring_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_resolution_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION NINE MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE HEALTH'
_OPEN_DRIFT_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE DRIFT'
_RESOLVE_DRIFT_PHRASE = 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE DRIFT'


class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)


class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_nine_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    audit_statement: str = Field(min_length=1, max_length=1800)
    audited_at: datetime | None = None


class DriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    trigger_audit_id: str = Field(min_length=1, max_length=160)
    open_phrase: str = Field(min_length=1, max_length=320)
    drift_reference: str = Field(min_length=1, max_length=300)
    drift_statement: str = Field(min_length=1, max_length=1800)


class DriftResolutionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    drift_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    corrected_successor_next_generation_nine_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    resolution_reference: str = Field(min_length=1, max_length=300)
    resolution_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_nine_monitoring_store() -> None:
    _monitoring_store.clear()
    _audit_store.clear()
    _drift_store.clear()
    _resolution_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _certification_by_id(certification_id: str) -> dict | None:
    return next((item for item in _certification_store.values() if item.get('certification_id') == certification_id), None)


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _audit_by_id(monitoring_id: str, audit_id: str) -> dict | None:
    return next((item for item in _audit_store.get(monitoring_id, []) if item.get('audit_id') == audit_id), None)


def _drift_by_id(drift_id: str) -> dict | None:
    return next((item for item in _drift_store.values() if item.get('drift_id') == drift_id), None)


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified successor-next-generation-nine monitoring approval required')
    existing = _monitoring_store.get(payload.certification_id)
    if existing is not None:
        return {'state': 'telegram-certified-successor-next-generation-nine-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certification = _certification_by_id(payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=409, detail='Stable v21.409 successor-next-generation-nine certification required')
    active_hash = certification.get('active_successor_next_generation_nine_hash')
    checks = {
        'certification_stable': certification.get('certification_state') == 'successor-next-generation-nine-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'active_hash_present': bool(active_hash),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Monitoring start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {'certification_id': certification['certification_id'], 'active_successor_next_generation_nine_hash': active_hash, 'audit_interval_days': payload.audit_interval_days, 'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(), 'checks': checks}
    monitoring = {'monitoring_id': str(uuid4()), **data, 'monitoring_state': 'certified-successor-next-generation-nine-monitoring-active', 'integrity_hash': _hash(data), 'immutable': True, 'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0}
    _monitoring_store[payload.certification_id] = monitoring
    return {'state': 'telegram-certified-successor-next-generation-nine-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/health/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine health audit required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    if monitoring.get('monitoring_state') != 'certified-successor-next-generation-nine-monitoring-active':
        raise HTTPException(status_code=409, detail='Active monitoring without open drift required')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    expected_hash = monitoring['active_successor_next_generation_nine_hash']
    hash_matches = payload.observed_successor_next_generation_nine_hash == expected_hash
    healthy = hash_matches and payload.control_state == 'healthy'
    audits = _audit_store.setdefault(monitoring['monitoring_id'], [])
    data = {'monitoring_id': monitoring['monitoring_id'], 'sequence': len(audits) + 1, 'expected_hash': expected_hash, 'observed_hash': payload.observed_successor_next_generation_nine_hash, 'hash_matches': hash_matches, 'control_state': payload.control_state, 'healthy': healthy, 'audit_statement': payload.audit_statement}
    audit = {'audit_id': str(uuid4()), **data, 'audit_state': 'successor-next-generation-nine-health-audit-passed' if healthy else 'successor-next-generation-nine-health-audit-failed', 'integrity_hash': _hash(data), 'immutable': True, 'audited_by': payload.actor, 'audited_at': audited_at.isoformat(), 'external_calls_made': 0}
    audits.append(audit)
    if healthy:
        monitoring['next_audit_due_at'] = (audited_at + timedelta(days=monitoring['audit_interval_days'])).isoformat()
    else:
        monitoring['monitoring_state'] = 'successor-next-generation-nine-drift-detected'
        monitoring['failed_trigger_audit_id'] = audit['audit_id']
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/open')
def open_drift(payload: DriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine drift opening required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    existing = _drift_store.get(monitoring['monitoring_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audit = _audit_by_id(monitoring['monitoring_id'], payload.trigger_audit_id)
    checks = {'monitoring_detected_drift': monitoring.get('monitoring_state') == 'successor-next-generation-nine-drift-detected', 'trigger_audit_failed': audit is not None and audit.get('healthy') is False, 'trigger_audit_immutable': audit is not None and audit.get('immutable') is True}
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Drift opening blocked', 'blockers': blockers})
    data = {'monitoring_id': monitoring['monitoring_id'], 'trigger_audit_id': audit['audit_id'], 'expected_hash': audit['expected_hash'], 'observed_hash': audit['observed_hash'], 'drift_reference': payload.drift_reference, 'drift_statement': payload.drift_statement, 'checks': checks}
    drift = {'drift_id': str(uuid4()), **data, 'drift_state': 'successor-next-generation-nine-drift-open', 'integrity_hash': _hash(data), 'immutable': True, 'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['monitoring_state'] = 'successor-next-generation-nine-drift-open'
    monitoring['drift_id'] = drift['drift_id']
    return {'state': 'telegram-successor-next-generation-nine-drift-open', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/resolve')
def resolve_drift(payload: DriftResolutionRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine drift resolution required')
    drift = _drift_by_id(payload.drift_id)
    if drift is None:
        raise HTTPException(status_code=404, detail='Open drift not found')
    existing = _resolution_store.get(drift['drift_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-drift-already-resolved', 'resolution': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(drift['monitoring_id'])
    checks = {'drift_open': drift.get('drift_state') == 'successor-next-generation-nine-drift-open', 'monitoring_drift_open': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-nine-drift-open', 'corrected_hash_matches': payload.corrected_successor_next_generation_nine_hash == drift['expected_hash'], 'controls_healthy': payload.control_state == 'healthy'}
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Drift resolution blocked', 'blockers': blockers})
    data = {'drift_id': drift['drift_id'], 'monitoring_id': drift['monitoring_id'], 'corrected_hash': payload.corrected_successor_next_generation_nine_hash, 'resolution_reference': payload.resolution_reference, 'resolution_statement': payload.resolution_statement, 'checks': checks}
    resolution = {'resolution_id': str(uuid4()), **data, 'resolution_state': 'successor-next-generation-nine-drift-resolved', 'integrity_hash': _hash(data), 'immutable': True, 'resolved_by': payload.actor, 'resolved_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _resolution_store[drift['drift_id']] = resolution
    drift['drift_state'] = 'successor-next-generation-nine-drift-resolved'
    drift['resolution_id'] = resolution['resolution_id']
    monitoring['monitoring_state'] = 'successor-next-generation-nine-drift-remediation-pending-validation'
    monitoring['resolution_id'] = resolution['resolution_id']
    return {'state': 'telegram-successor-next-generation-nine-drift-resolved', 'resolution': resolution, 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'successor-next-generation-nine-drift-remediation-validation-recertification-renewed-baseline'}


@router.get('/status')
def status() -> dict:
    return {'monitorings': len(_monitoring_store), 'audits': sum(len(items) for items in _audit_store.values()), 'drifts': len(_drift_store), 'resolutions': len(_resolution_store), 'external_calls_made': 0, 'mode': 'certified-successor-next-generation-nine-monitoring-audit-drift-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.410</title></head><body><h1>AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION NINE MONITORING COMMAND CENTER</h1><p>Long-term monitoring, periodic succession-health audit and drift governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
