from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_baseline_stabilization_v21_354 import _certification_store
from app.api.routes.auron_demo1_telegram_expired_baseline_restoration_v21_353 import _successor_store
from app.api.routes.auron_demo1_telegram_renewed_assurance_continuity_v21_352 import _continuity_store

router = APIRouter(prefix='/auron/demo1/v21.355', tags=['auron-demo1-telegram-successor-baseline-monitoring'])
_monitoring_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM CERTIFIED SUCCESSOR MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSION HEALTH'
_OPEN_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR BASELINE DRIFT'
_RESOLVE_PHRASE = 'RESOLVE AURON TELEGRAM SUCCESSOR BASELINE DRIFT'

class CertifiedSuccessorMonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=90, ge=1, le=3650)

class SuccessionHealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    audit_statement: str = Field(min_length=1, max_length=1800)
    audited_at: datetime | None = None

class SuccessorDriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    open_phrase: str = Field(min_length=1, max_length=320)
    severity: str = Field(pattern='^(low|medium|high|critical)$')
    reason: str = Field(min_length=1, max_length=1800)

class SuccessorDriftResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    resolve_phrase: str = Field(min_length=1, max_length=320)
    resolution: str = Field(min_length=1, max_length=1800)
    corrected_successor_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')

def reset_telegram_successor_baseline_monitoring_store() -> None:
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
def start_monitoring(payload: CertifiedSuccessorMonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified successor monitoring approval required')
    existing = _monitoring_store.get(payload.certification_id)
    if existing is not None:
        return {'state': 'telegram-certified-successor-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certification = _certification_by_id(payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=404, detail='Successor succession certification not found')
    successor = next((item for item in _successor_store.values() if item.get('successor_id') == certification.get('successor_id')), None)
    continuity = next((item for item in _continuity_store.values() if item.get('continuity_id') == certification.get('continuity_id')), None)
    checks = {
        'certification_stable': certification.get('certification_state') == 'successor-baseline-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'successor_certified': bool(successor and successor.get('successor_state') == 'successor-assurance-baseline-certified-stable'),
        'continuity_active': bool(continuity and continuity.get('continuity_state') == 'renewed-assurance-continuity-active'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certified successor monitoring blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'certification_id': certification['certification_id'],
        'successor_id': certification['successor_id'],
        'continuity_id': certification['continuity_id'],
        'successor_baseline_hash': certification['successor_baseline_hash'],
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    monitoring = {'monitoring_id': str(uuid4()), **data, 'monitoring_state': 'certified-successor-monitoring-active', 'integrity_hash': _hash(data), 'audit_count': 0, 'immutable': True, 'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0}
    _monitoring_store[payload.certification_id] = monitoring
    return {'state': 'telegram-certified-successor-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}

@router.post('/health/audit')
def audit_health(payload: SuccessionHealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit succession-health audit approval required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Certified successor monitoring not found')
    drift = _drift_store.get(monitoring['monitoring_id'])
    if drift and drift.get('drift_state') == 'successor-baseline-drift-open':
        raise HTTPException(status_code=409, detail='Open successor drift blocks routine audit')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    hash_matches = payload.observed_successor_hash == monitoring['successor_baseline_hash']
    healthy = hash_matches and payload.continuity_state == 'healthy'
    sequence = monitoring['audit_count'] + 1
    data = {'monitoring_id': monitoring['monitoring_id'], 'sequence': sequence, 'expected_successor_hash': monitoring['successor_baseline_hash'], 'observed_successor_hash': payload.observed_successor_hash, 'hash_matches': hash_matches, 'continuity_state': payload.continuity_state, 'healthy': healthy, 'audit_statement': payload.audit_statement}
    audit = {'audit_id': str(uuid4()), **data, 'audit_state': 'succession-health-certified' if healthy else 'successor-baseline-drift-detected', 'integrity_hash': _hash(data), 'immutable': True, 'audited_by': payload.actor, 'audited_at': audited_at.isoformat(), 'external_calls_made': 0}
    _audit_store.setdefault(monitoring['monitoring_id'], []).append(audit)
    monitoring.update(audit_count=sequence, last_audit_id=audit['audit_id'], next_audit_due_at=(audited_at + timedelta(days=monitoring['audit_interval_days'])).isoformat(), monitoring_state='certified-successor-monitoring-active' if healthy else 'successor-drift-governance-required')
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}

@router.post('/drift/open')
def open_drift(payload: SuccessorDriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor drift opening approval required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Certified successor monitoring not found')
    existing = _drift_store.get(monitoring['monitoring_id'])
    if existing and existing.get('drift_state') == 'successor-baseline-drift-open':
        return {'state': 'telegram-successor-baseline-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    latest = (_audit_store.get(monitoring['monitoring_id']) or [None])[-1]
    if latest is None or latest.get('audit_state') != 'successor-baseline-drift-detected':
        raise HTTPException(status_code=409, detail='Detected successor drift required')
    data = {'monitoring_id': monitoring['monitoring_id'], 'trigger_audit_id': latest['audit_id'], 'severity': payload.severity, 'reason': payload.reason}
    drift = {'drift_id': str(uuid4()), **data, 'drift_state': 'successor-baseline-drift-open', 'integrity_hash': _hash(data), 'immutable': True, 'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['monitoring_state'] = 'successor-baseline-drift-open'
    return {'state': 'telegram-successor-baseline-drift-opened', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}

@router.post('/drift/resolve')
def resolve_drift(payload: SuccessorDriftResolveRequest) -> dict:
    if payload.resolve_phrase != _RESOLVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor drift resolution approval required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    if monitoring is None or drift is None:
        raise HTTPException(status_code=404, detail='Open successor drift not found')
    if drift.get('drift_state') == 'successor-baseline-drift-resolved':
        return {'state': 'telegram-successor-baseline-drift-already-resolved', 'drift': drift, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc)
    drift.update(drift_state='successor-baseline-drift-resolved', resolution=payload.resolution, corrected_successor_hash=payload.corrected_successor_hash, resolved_by=payload.actor, resolved_at=now.isoformat())
    monitoring.update(successor_baseline_hash=payload.corrected_successor_hash, monitoring_state='certified-successor-monitoring-active', next_audit_due_at=(now + timedelta(days=monitoring['audit_interval_days'])).isoformat())
    return {'state': 'telegram-successor-baseline-drift-resolved', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'successor-drift-remediation-validation-and-recertification'}

@router.get('/status')
def status() -> dict:
    return {'monitoring_records': len(_monitoring_store), 'succession_health_audits': sum(len(items) for items in _audit_store.values()), 'open_successor_drifts': sum(1 for item in _drift_store.values() if item.get('drift_state') == 'successor-baseline-drift-open'), 'external_calls_made': 0, 'mode': 'certified-successor-long-term-monitoring-succession-health-audit-drift-governance'}

@router.get('/monitoring')
def list_monitoring() -> dict:
    return {'count': len(_monitoring_store), 'items': list(_monitoring_store.values()), 'external_calls_made': 0}

@router.get('/audits')
def list_audits() -> dict:
    items = [item for audits in _audit_store.values() for item in audits]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}

@router.get('/drifts')
def list_drifts() -> dict:
    return {'count': len(_drift_store), 'items': list(_drift_store.values()), 'external_calls_made': 0}

@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_successor_baseline_stabilization_v21_354 import command_center as previous
    return previous().replace('v21.354', 'v21.355').replace('AURON TELEGRAM SUCCESSOR BASELINE STABILIZATION COMMAND CENTER', 'AURON TELEGRAM SUCCESSOR BASELINE MONITORING COMMAND CENTER')
