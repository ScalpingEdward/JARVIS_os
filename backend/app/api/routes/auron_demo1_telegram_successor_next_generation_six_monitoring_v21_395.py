from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_six_stabilization_v21_394 import (
    _certification_store,
    _stabilization_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.395',
    tags=['auron-demo1-telegram-successor-next-generation-six-monitoring'],
)

_monitoring_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_resolution_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION SIX MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX HEALTH'
_OPEN_DRIFT_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX DRIFT'
_RESOLVE_DRIFT_PHRASE = 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX DRIFT'


class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)


class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_six_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    statement: str = Field(min_length=1, max_length=1800)
    audited_at: datetime | None = None


class DriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_id: str = Field(min_length=1, max_length=160)
    open_phrase: str = Field(min_length=1, max_length=320)
    drift_reason: str = Field(min_length=1, max_length=1800)


class DriftResolutionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    drift_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    corrected_successor_next_generation_six_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    remediation_reference: str = Field(min_length=1, max_length=300)
    resolution_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_six_monitoring_store() -> None:
    _monitoring_store.clear()
    _audit_store.clear()
    _drift_store.clear()
    _resolution_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _stabilization_by_id(stabilization_id: str) -> dict | None:
    return next((item for item in _stabilization_store.values() if item.get('stabilization_id') == stabilization_id), None)


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _drift_by_id(drift_id: str) -> dict | None:
    return next((item for item in _drift_store.values() if item.get('drift_id') == drift_id), None)


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified successor-next-generation-six monitoring approval required')
    existing = _monitoring_store.get(payload.stabilization_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-six-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    stabilization = _stabilization_by_id(payload.stabilization_id)
    certification = _certification_store.get(payload.stabilization_id)
    if stabilization is None or certification is None:
        raise HTTPException(status_code=409, detail='Stable v21.394 successor-next-generation-six certification required')
    active_hash = certification.get('active_successor_next_generation_six_hash')
    checks = {
        'stabilization_certified': stabilization.get('stabilization_state') == 'successor-next-generation-six-stabilization-certified',
        'certification_stable': certification.get('certification_state') == 'successor-next-generation-six-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'active_hash_present': bool(active_hash),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Monitoring start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'stabilization_id': payload.stabilization_id,
        'certification_id': certification['certification_id'],
        'active_successor_next_generation_six_hash': active_hash,
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    monitoring = {
        'monitoring_id': str(uuid4()), **data,
        'monitoring_state': 'certified-successor-next-generation-six-monitoring-active',
        'audit_count': 0, 'open_drift_id': None,
        'integrity_hash': _hash(data), 'immutable': True,
        'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0,
    }
    _monitoring_store[payload.stabilization_id] = monitoring
    return {'state': 'telegram-certified-successor-next-generation-six-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/health/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-six health audit required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    if monitoring.get('open_drift_id'):
        raise HTTPException(status_code=409, detail='Open successor-next-generation-six drift blocks routine health audits')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    expected_hash = monitoring['active_successor_next_generation_six_hash']
    hash_matches = payload.observed_successor_next_generation_six_hash == expected_hash
    healthy = hash_matches and payload.continuity_state == 'healthy'
    audits = _audit_store.setdefault(monitoring['monitoring_id'], [])
    data = {
        'monitoring_id': monitoring['monitoring_id'], 'sequence': len(audits) + 1,
        'expected_hash': expected_hash, 'observed_hash': payload.observed_successor_next_generation_six_hash,
        'hash_matches': hash_matches, 'continuity_state': payload.continuity_state,
        'healthy': healthy, 'statement': payload.statement,
    }
    audit = {
        'audit_id': str(uuid4()), **data,
        'audit_state': 'successor-next-generation-six-health-verified' if healthy else 'successor-next-generation-six-health-failed-drift-required',
        'integrity_hash': _hash(data), 'immutable': True,
        'audited_by': payload.actor, 'audited_at': audited_at.isoformat(), 'external_calls_made': 0,
    }
    audits.append(audit)
    monitoring.update(
        audit_count=len(audits), last_audit_id=audit['audit_id'],
        next_audit_due_at=(audited_at + timedelta(days=monitoring['audit_interval_days'])).isoformat(),
        monitoring_state='certified-successor-next-generation-six-monitoring-active' if healthy else 'successor-next-generation-six-drift-opening-required',
    )
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/open')
def open_drift(payload: DriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-six drift opening required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    existing = _drift_store.get(monitoring['monitoring_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-six-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audit = next((item for item in _audit_store.get(monitoring['monitoring_id'], []) if item.get('audit_id') == payload.audit_id), None)
    if audit is None or audit.get('healthy') is not False:
        raise HTTPException(status_code=409, detail='Failed immutable trigger audit required')
    data = {
        'monitoring_id': monitoring['monitoring_id'], 'trigger_audit_id': audit['audit_id'],
        'expected_hash': audit['expected_hash'], 'observed_hash': audit['observed_hash'], 'drift_reason': payload.drift_reason,
    }
    drift = {
        'drift_id': str(uuid4()), **data, 'drift_state': 'successor-next-generation-six-drift-open',
        'integrity_hash': _hash(data), 'immutable': True,
        'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0,
    }
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['open_drift_id'] = drift['drift_id']
    monitoring['monitoring_state'] = 'successor-next-generation-six-drift-open-remediation-required'
    return {'state': 'telegram-successor-next-generation-six-drift-opened', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/resolve')
def resolve_drift(payload: DriftResolutionRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-six drift resolution required')
    drift = _drift_by_id(payload.drift_id)
    if drift is None:
        raise HTTPException(status_code=404, detail='Drift not found')
    existing = _resolution_store.get(drift['drift_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-six-drift-already-resolved', 'resolution': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(drift['monitoring_id'])
    if monitoring is None or drift.get('drift_state') != 'successor-next-generation-six-drift-open':
        raise HTTPException(status_code=409, detail='Open drift and monitoring evidence required')
    checks = {
        'controls_healthy': payload.control_state == 'healthy',
        'corrected_hash_matches_baseline': payload.corrected_successor_next_generation_six_hash == monitoring['active_successor_next_generation_six_hash'],
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Drift resolution blocked', 'blockers': blockers})
    data = {
        'drift_id': drift['drift_id'], 'monitoring_id': monitoring['monitoring_id'],
        'corrected_hash': payload.corrected_successor_next_generation_six_hash,
        'control_state': payload.control_state, 'remediation_reference': payload.remediation_reference,
        'resolution_statement': payload.resolution_statement, 'checks': checks,
    }
    resolution = {
        'resolution_id': str(uuid4()), **data,
        'resolution_state': 'successor-next-generation-six-drift-resolved-awaiting-recertification',
        'integrity_hash': _hash(data), 'immutable': True,
        'resolved_by': payload.actor, 'resolved_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0,
    }
    _resolution_store[drift['drift_id']] = resolution
    drift['drift_state'] = 'successor-next-generation-six-drift-resolved'
    drift['resolution_id'] = resolution['resolution_id']
    monitoring['open_drift_id'] = None
    monitoring['monitoring_state'] = 'successor-next-generation-six-drift-resolved-recertification-required'
    return {'state': 'telegram-successor-next-generation-six-drift-resolved', 'resolution': resolution, 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.get('/status')
def status() -> dict:
    return {
        'monitoring_records': len(_monitoring_store),
        'health_audits': sum(len(items) for items in _audit_store.values()),
        'drifts': len(_drift_store), 'resolutions': len(_resolution_store),
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-six-monitoring-audit-drift-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.395</title></head><body><h1>AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION SIX MONITORING COMMAND CENTER</h1><p>Periodic succession-health audit and drift governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
