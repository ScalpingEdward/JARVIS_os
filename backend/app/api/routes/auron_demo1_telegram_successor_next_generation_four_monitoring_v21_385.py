from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_four_stabilization_v21_384 import (
    _certification_store,
    _stabilization_store,
)
from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_three_restoration_v21_383 import (
    _succession_store,
)
from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_three_continuity_v21_382 import (
    _continuity_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.385',
    tags=['auron-demo1-telegram-successor-next-generation-four-monitoring'],
)

_monitoring_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_resolution_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION FOUR MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR HEALTH'
_OPEN_DRIFT_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR DRIFT'
_RESOLVE_DRIFT_PHRASE = 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR DRIFT'


class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)


class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_four_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    statement: str = Field(min_length=1, max_length=1800)
    audited_at: datetime | None = None


class DriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    drift_phrase: str = Field(min_length=1, max_length=320)
    trigger_audit_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=1800)


class DriftResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    corrected_successor_next_generation_four_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    remediation_reference: str = Field(min_length=1, max_length=300)
    remediation_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_four_monitoring_store() -> None:
    _monitoring_store.clear()
    _audit_store.clear()
    _drift_store.clear()
    _resolution_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _certification_for_continuity(continuity_id: str) -> dict | None:
    stabilization = _stabilization_store.get(continuity_id)
    if stabilization is None:
        return None
    return _certification_store.get(stabilization.get('stabilization_id'))


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified successor-next-generation-four monitoring approval required')
    existing = _monitoring_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-certified-successor-next-generation-four-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    succession = _succession_store.get(payload.continuity_id)
    certification = _certification_for_continuity(payload.continuity_id)
    if continuity is None or succession is None or certification is None:
        raise HTTPException(status_code=409, detail='Stable v21.384 successor-next-generation-four certification required')
    active_hash = succession.get('successor_next_generation_four_hash')
    checks = {
        'certification_stable': certification.get('certification_state') == 'successor-next-generation-four-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'succession_certified': succession.get('succession_state') == 'successor-next-generation-four-baseline-certified-stable',
        'continuity_active': continuity.get('continuity_state') == 'successor-next-generation-four-continuity-active',
        'active_hash_consistent': bool(active_hash) and active_hash == continuity.get('active_baseline_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Monitoring blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'continuity_id': payload.continuity_id,
        'succession_id': succession['succession_id'],
        'certification_id': certification['certification_id'],
        'active_successor_next_generation_four_hash': active_hash,
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    monitoring = {
        'monitoring_id': str(uuid4()),
        **data,
        'monitoring_state': 'certified-successor-next-generation-four-monitoring-active',
        'audit_count': 0,
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _monitoring_store[payload.continuity_id] = monitoring
    return {'state': 'telegram-certified-successor-next-generation-four-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/health/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-four health audit required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    open_drift = _drift_store.get(monitoring['monitoring_id'])
    if open_drift and open_drift.get('drift_state') == 'successor-next-generation-four-drift-open':
        raise HTTPException(status_code=409, detail='Open drift blocks routine audits')
    if monitoring.get('monitoring_state') != 'certified-successor-next-generation-four-monitoring-active':
        raise HTTPException(status_code=409, detail='Monitoring is not active')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    audits = _audit_store.setdefault(monitoring['monitoring_id'], [])
    expected_hash = monitoring['active_successor_next_generation_four_hash']
    hash_matches = payload.observed_successor_next_generation_four_hash == expected_hash
    healthy = hash_matches and payload.continuity_state == 'healthy'
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'continuity_id': monitoring['continuity_id'],
        'sequence': len(audits) + 1,
        'expected_hash': expected_hash,
        'observed_hash': payload.observed_successor_next_generation_four_hash,
        'hash_matches': hash_matches,
        'continuity_state': payload.continuity_state,
        'healthy': healthy,
        'statement': payload.statement,
    }
    audit = {
        'audit_id': str(uuid4()),
        **data,
        'audit_state': 'successor-next-generation-four-health-verified' if healthy else 'successor-next-generation-four-drift-detected',
        'integrity_hash': _hash(data),
        'immutable': True,
        'audited_by': payload.actor,
        'audited_at': audited_at.isoformat(),
        'external_calls_made': 0,
    }
    audits.append(audit)
    monitoring.update(
        audit_count=len(audits),
        last_audit_id=audit['audit_id'],
        next_audit_due_at=(audited_at + timedelta(days=monitoring['audit_interval_days'])).isoformat(),
        monitoring_state='certified-successor-next-generation-four-monitoring-active' if healthy else 'successor-next-generation-four-drift-review-required',
    )
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/open')
def open_drift(payload: DriftOpenRequest) -> dict:
    if payload.drift_phrase != _OPEN_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit drift opening required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    existing = _drift_store.get(monitoring['monitoring_id'])
    if existing and existing.get('drift_state') == 'successor-next-generation-four-drift-open':
        return {'state': 'telegram-successor-next-generation-four-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audit = next((item for item in _audit_store.get(monitoring['monitoring_id'], []) if item.get('audit_id') == payload.trigger_audit_id), None)
    if audit is None or audit.get('healthy') is not False:
        raise HTTPException(status_code=409, detail='A failed immutable trigger audit is required')
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'continuity_id': monitoring['continuity_id'],
        'trigger_audit_id': audit['audit_id'],
        'expected_hash': audit['expected_hash'],
        'observed_hash': audit['observed_hash'],
        'reason': payload.reason,
    }
    drift = {
        'drift_id': str(uuid4()),
        **data,
        'drift_state': 'successor-next-generation-four-drift-open',
        'integrity_hash': _hash(data),
        'immutable': True,
        'opened_by': payload.actor,
        'opened_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['monitoring_state'] = 'successor-next-generation-four-drift-open'
    return {'state': 'telegram-successor-next-generation-four-drift-opened', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/resolve')
def resolve_drift(payload: DriftResolveRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit drift resolution required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    drift = _drift_store.get(monitoring['monitoring_id'])
    if drift is None or drift.get('drift_state') != 'successor-next-generation-four-drift-open':
        raise HTTPException(status_code=409, detail='Open drift required')
    existing = _resolution_store.get(monitoring['monitoring_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-four-drift-already-resolved', 'resolution': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    checks = {
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
        'controls_healthy': payload.control_state == 'healthy',
        'corrected_hash_present': bool(payload.corrected_successor_next_generation_four_hash),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Drift resolution blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'drift_id': drift['drift_id'],
        'previous_hash': monitoring['active_successor_next_generation_four_hash'],
        'corrected_hash': payload.corrected_successor_next_generation_four_hash,
        'control_state': payload.control_state,
        'remediation_reference': payload.remediation_reference,
        'remediation_statement': payload.remediation_statement,
        'checks': checks,
    }
    resolution = {
        'resolution_id': str(uuid4()),
        **data,
        'resolution_state': 'successor-next-generation-four-drift-resolved-awaiting-recertification',
        'integrity_hash': _hash(data),
        'immutable': True,
        'resolved_by': payload.actor,
        'resolved_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _resolution_store[monitoring['monitoring_id']] = resolution
    drift.update(drift_state='successor-next-generation-four-drift-resolved', resolution_id=resolution['resolution_id'])
    monitoring.update(
        monitoring_state='successor-next-generation-four-recertification-required',
        corrected_successor_next_generation_four_hash=payload.corrected_successor_next_generation_four_hash,
    )
    return {
        'state': 'telegram-successor-next-generation-four-drift-resolved',
        'resolution': resolution,
        'drift': drift,
        'monitoring': monitoring,
        'external_calls_made': 0,
        'next_layer': 'successor-next-generation-four-recertification-and-renewed-baseline',
    }


@router.get('/status')
def status() -> dict:
    return {
        'monitoring_records': len(_monitoring_store),
        'health_audits': sum(len(items) for items in _audit_store.values()),
        'open_drifts': sum(1 for item in _drift_store.values() if item.get('drift_state') == 'successor-next-generation-four-drift-open'),
        'drift_resolutions': len(_resolution_store),
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-four-monitoring-audit-drift-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.385</title></head><body><h1>AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION FOUR MONITORING COMMAND CENTER</h1><p>Periodic succession-health audit and drift governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
