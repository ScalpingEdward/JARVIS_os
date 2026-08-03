from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_stabilization_v21_364 import _certification_store
from app.api.routes.auron_demo1_telegram_expired_renewed_next_successor_restoration_v21_363 import _succession_store
from app.api.routes.auron_demo1_telegram_renewed_next_successor_continuity_v21_362 import _continuity_store

router = APIRouter(prefix='/auron/demo1/v21.365', tags=['auron-demo1-telegram-successor-next-monitoring'])
_monitoring_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT HEALTH'
_OPEN_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR NEXT DRIFT'
_RESOLVE_PHRASE = 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT DRIFT'


class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=90, ge=1, le=3650)


class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    audit_statement: str = Field(min_length=1, max_length=1800)
    audited_at: datetime | None = None


class DriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    open_phrase: str = Field(min_length=1, max_length=320)
    severity: str = Field(pattern='^(low|medium|high|critical)$')
    reason: str = Field(min_length=1, max_length=1800)


class DriftResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    resolve_phrase: str = Field(min_length=1, max_length=320)
    corrected_successor_next_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    resolution_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_monitoring_store() -> None:
    _monitoring_store.clear()
    _audit_store.clear()
    _drift_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _certification_by_id(certification_id: str) -> dict | None:
    return next((item for item in _certification_store.values() if item.get('certification_id') == certification_id), None)


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified successor-next monitoring approval required')
    existing = _monitoring_store.get(payload.certification_id)
    if existing is not None:
        return {'state': 'telegram-certified-successor-next-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certification = _certification_by_id(payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=404, detail='Successor-next succession certification not found')
    succession = next((item for item in _succession_store.values() if item.get('succession_id') == certification.get('succession_id')), None)
    continuity = next((item for item in _continuity_store.values() if item.get('continuity_id') == certification.get('continuity_id')), None)
    checks = {
        'certification_stable': certification.get('certification_state') == 'successor-next-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'succession_certified': bool(succession and succession.get('succession_state') == 'successor-next-baseline-certified-stable'),
        'continuity_active': bool(continuity and continuity.get('continuity_state') == 'renewed-next-successor-continuity-active'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certified successor-next monitoring blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'certification_id': certification['certification_id'],
        'succession_id': certification['succession_id'],
        'continuity_id': certification['continuity_id'],
        'successor_next_hash': certification['successor_next_hash'],
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    monitoring = {'monitoring_id': str(uuid4()), **data, 'monitoring_state': 'certified-successor-next-monitoring-active', 'audit_count': 0, 'integrity_hash': _hash(data), 'immutable': True, 'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0}
    _monitoring_store[payload.certification_id] = monitoring
    return {'state': 'telegram-certified-successor-next-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/health/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next health audit required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Certified successor-next monitoring not found')
    drift = _drift_store.get(monitoring['monitoring_id'])
    if drift and drift.get('drift_state') == 'successor-next-drift-open':
        raise HTTPException(status_code=409, detail='Open successor-next drift blocks routine audit')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    hash_matches = payload.observed_successor_next_hash == monitoring['successor_next_hash']
    healthy = hash_matches and payload.continuity_state == 'healthy'
    sequence = monitoring['audit_count'] + 1
    data = {'monitoring_id': monitoring['monitoring_id'], 'sequence': sequence, 'expected_successor_next_hash': monitoring['successor_next_hash'], 'observed_successor_next_hash': payload.observed_successor_next_hash, 'hash_matches': hash_matches, 'continuity_state': payload.continuity_state, 'healthy': healthy, 'audit_statement': payload.audit_statement}
    audit = {'audit_id': str(uuid4()), **data, 'audit_state': 'successor-next-health-certified' if healthy else 'successor-next-drift-detected', 'integrity_hash': _hash(data), 'immutable': True, 'audited_by': payload.actor, 'audited_at': audited_at.isoformat(), 'external_calls_made': 0}
    _audit_store.setdefault(monitoring['monitoring_id'], []).append(audit)
    monitoring.update(audit_count=sequence, last_audit_id=audit['audit_id'], next_audit_due_at=(audited_at + timedelta(days=monitoring['audit_interval_days'])).isoformat(), monitoring_state='certified-successor-next-monitoring-active' if healthy else 'successor-next-drift-governance-required')
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/open')
def open_drift(payload: DriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next drift opening required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Certified successor-next monitoring not found')
    existing = _drift_store.get(monitoring['monitoring_id'])
    if existing and existing.get('drift_state') == 'successor-next-drift-open':
        return {'state': 'telegram-successor-next-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    latest = (_audit_store.get(monitoring['monitoring_id']) or [None])[-1]
    if latest is None or latest.get('audit_state') != 'successor-next-drift-detected':
        raise HTTPException(status_code=409, detail='Detected successor-next drift required')
    data = {'monitoring_id': monitoring['monitoring_id'], 'trigger_audit_id': latest['audit_id'], 'severity': payload.severity, 'reason': payload.reason}
    drift = {'drift_id': str(uuid4()), **data, 'drift_state': 'successor-next-drift-open', 'integrity_hash': _hash(data), 'immutable': True, 'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['monitoring_state'] = 'successor-next-drift-open'
    return {'state': 'telegram-successor-next-drift-opened', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/resolve')
def resolve_drift(payload: DriftResolveRequest) -> dict:
    if payload.resolve_phrase != _RESOLVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next drift resolution required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    if monitoring is None or drift is None:
        raise HTTPException(status_code=404, detail='Open successor-next drift not found')
    if drift.get('drift_state') == 'successor-next-drift-resolved':
        return {'state': 'telegram-successor-next-drift-already-resolved', 'drift': drift, 'idempotent_replay': True, 'external_calls_made': 0}
    if payload.control_state != 'healthy':
        raise HTTPException(status_code=409, detail='Healthy controls required for successor-next drift resolution')
    now = datetime.now(timezone.utc)
    resolution_data = {'drift_id': drift['drift_id'], 'corrected_successor_next_hash': payload.corrected_successor_next_hash, 'control_state': payload.control_state, 'resolution_statement': payload.resolution_statement}
    drift.update(drift_state='successor-next-drift-resolved', corrected_successor_next_hash=payload.corrected_successor_next_hash, control_state=payload.control_state, resolution_statement=payload.resolution_statement, resolution_integrity_hash=_hash(resolution_data), resolved_by=payload.actor, resolved_at=now.isoformat())
    monitoring.update(successor_next_hash=payload.corrected_successor_next_hash, monitoring_state='certified-successor-next-monitoring-active', next_audit_due_at=(now + timedelta(days=monitoring['audit_interval_days'])).isoformat())
    return {'state': 'telegram-successor-next-drift-resolved', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'successor-next-drift-remediation-validation-and-recertification'}


@router.get('/status')
def status() -> dict:
    return {'monitoring_records': len(_monitoring_store), 'succession_health_audits': sum(len(items) for items in _audit_store.values()), 'open_successor_next_drifts': sum(1 for item in _drift_store.values() if item.get('drift_state') == 'successor-next-drift-open'), 'external_calls_made': 0, 'mode': 'certified-successor-next-monitoring-periodic-health-audit-drift-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_successor_next_stabilization_v21_364 import command_center as previous
    return previous().replace('v21.364', 'v21.365').replace('AURON TELEGRAM SUCCESSOR NEXT STABILIZATION COMMAND CENTER', 'AURON TELEGRAM SUCCESSOR NEXT MONITORING COMMAND CENTER')
