from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_twenty_eight_restoration_v21_467 import _succession_store
from app.api.routes.auron_demo1_telegram_successor_next_generation_twenty_seven_monitoring_v21_465 import _monitor_store as _legacy_monitor_store

router = APIRouter(
    prefix='/auron/demo1/v21.468',
    tags=['auron-demo1-telegram-successor-next-generation-twenty-eight-monitoring'],
)

_monitor_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY EIGHT MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY EIGHT HEALTH'
_OPEN_DRIFT_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY EIGHT DRIFT'
_CERTIFY_BASELINE_PHRASE = 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY EIGHT RENEWED BASELINE'


class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)


class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_twenty_eight_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
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


class RenewedBaselineCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_twenty_eight_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    baseline_reference: str = Field(min_length=1, max_length=300)
    baseline_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_twenty_eight_monitoring_store() -> None:
    _monitor_store.clear()
    _audit_store.clear()
    _drift_store.clear()
    _baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _find(store: dict[str, dict], key: str, value: str) -> dict | None:
    return next((item for item in store.values() if item.get(key) == value), None)


def _audit_by_id(monitoring_id: str, audit_id: str) -> dict | None:
    return next((item for item in _audit_store.get(monitoring_id, []) if item.get('audit_id') == audit_id), None)


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-eight monitoring approval required')
    existing = _monitor_store.get(payload.certification_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-eight-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certification = _find(_succession_store, 'certification_id', payload.certification_id)
    if certification is None:
        raise HTTPException(404, 'Stable successor-next-generation-twenty-eight certification not found')
    legacy = _find(_legacy_monitor_store, 'monitoring_id', certification['monitoring_id'])
    active_hash = certification.get('active_successor_next_generation_twenty_eight_hash')
    checks = {
        'certification_stable': certification.get('certification_state') == 'successor-next-generation-twenty-eight-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'legacy_monitor_pending': legacy is not None and legacy.get('monitoring_state') == 'certified-successor-next-generation-twenty-eight-monitoring-pending',
        'active_hash_aligned': legacy is not None and legacy.get('active_successor_next_generation_twenty_eight_hash') == active_hash,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-eight monitoring start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'certification_id': certification['certification_id'],
        'legacy_monitoring_id': certification['monitoring_id'],
        'active_successor_next_generation_twenty_eight_hash': active_hash,
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    monitoring = {
        'monitoring_id': str(uuid4()), **data,
        'monitoring_state': 'successor-next-generation-twenty-eight-monitoring-active',
        'integrity_hash': _hash(data), 'immutable': True,
        'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0,
    }
    _monitor_store[payload.certification_id] = monitoring
    legacy['monitoring_state'] = 'certified-successor-next-generation-twenty-eight-monitoring-active'
    legacy['successor_next_generation_twenty_eight_monitoring_id'] = monitoring['monitoring_id']
    return {'state': 'telegram-successor-next-generation-twenty-eight-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/health/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-eight health audit required')
    monitoring = _find(_monitor_store, 'monitoring_id', payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(404, 'Successor-next-generation-twenty-eight monitoring not found')
    if monitoring.get('monitoring_state') != 'successor-next-generation-twenty-eight-monitoring-active':
        raise HTTPException(409, 'Active successor-next-generation-twenty-eight monitoring required')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    expected = monitoring['active_successor_next_generation_twenty_eight_hash']
    hash_matches = payload.observed_successor_next_generation_twenty_eight_hash == expected
    healthy = hash_matches and payload.control_state == 'healthy'
    audits = _audit_store.setdefault(monitoring['monitoring_id'], [])
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'sequence': len(audits) + 1,
        'expected_hash': expected,
        'observed_hash': payload.observed_successor_next_generation_twenty_eight_hash,
        'hash_matches': hash_matches,
        'control_state': payload.control_state,
        'healthy': healthy,
        'audit_statement': payload.audit_statement,
    }
    audit = {
        'audit_id': str(uuid4()), **data,
        'audit_state': 'successor-next-generation-twenty-eight-health-audit-passed' if healthy else 'successor-next-generation-twenty-eight-health-audit-failed',
        'integrity_hash': _hash(data), 'immutable': True,
        'audited_by': payload.actor, 'audited_at': audited_at.isoformat(), 'external_calls_made': 0,
    }
    audits.append(audit)
    if healthy:
        monitoring['next_audit_due_at'] = (audited_at + timedelta(days=monitoring['audit_interval_days'])).isoformat()
    else:
        monitoring['monitoring_state'] = 'successor-next-generation-twenty-eight-drift-detected'
        monitoring['failed_trigger_audit_id'] = audit['audit_id']
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/open')
def open_drift(payload: DriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_DRIFT_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-eight drift opening required')
    monitoring = _find(_monitor_store, 'monitoring_id', payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(404, 'Successor-next-generation-twenty-eight monitoring not found')
    existing = _drift_store.get(monitoring['monitoring_id'])
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-eight-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audit = _audit_by_id(monitoring['monitoring_id'], payload.trigger_audit_id)
    checks = {
        'monitoring_detected_drift': monitoring.get('monitoring_state') == 'successor-next-generation-twenty-eight-drift-detected',
        'trigger_audit_failed': audit is not None and audit.get('healthy') is False,
        'trigger_audit_immutable': audit is not None and audit.get('immutable') is True and bool(audit.get('integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-eight drift opening blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'trigger_audit_id': audit['audit_id'],
        'expected_hash': audit['expected_hash'],
        'observed_hash': audit['observed_hash'],
        'drift_reference': payload.drift_reference,
        'drift_statement': payload.drift_statement,
        'checks': checks,
    }
    drift = {
        'drift_id': str(uuid4()), **data,
        'drift_state': 'successor-next-generation-twenty-eight-drift-open',
        'integrity_hash': _hash(data), 'immutable': True,
        'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0,
    }
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['monitoring_state'] = 'successor-next-generation-twenty-eight-drift-open'
    monitoring['drift_id'] = drift['drift_id']
    return {'state': 'telegram-successor-next-generation-twenty-eight-drift-open', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/baseline/certify')
def certify_renewed_baseline(payload: RenewedBaselineCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_BASELINE_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-eight renewed baseline certification required')
    monitoring = _find(_monitor_store, 'monitoring_id', payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(404, 'Successor-next-generation-twenty-eight monitoring not found')
    existing = _baseline_store.get(monitoring['monitoring_id'])
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-eight-renewed-baseline-already-certified', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    drift = _drift_store.get(monitoring['monitoring_id'])
    expected = monitoring['active_successor_next_generation_twenty_eight_hash']
    checks = {
        'monitoring_active': monitoring.get('monitoring_state') == 'successor-next-generation-twenty-eight-monitoring-active',
        'monitoring_immutable': monitoring.get('immutable') is True and bool(monitoring.get('integrity_hash')),
        'no_open_drift': drift is None,
        'hash_matches': payload.observed_successor_next_generation_twenty_eight_hash == expected,
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Renewed baseline certification blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'active_successor_next_generation_twenty_eight_hash': expected,
        'baseline_reference': payload.baseline_reference,
        'baseline_statement': payload.baseline_statement,
        'checks': checks,
    }
    baseline = {
        'baseline_id': str(uuid4()), **data,
        'baseline_state': 'successor-next-generation-twenty-eight-renewed-baseline-certified-active',
        'integrity_hash': _hash(data), 'immutable': True,
        'certified_by': payload.actor, 'certified_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0,
    }
    _baseline_store[monitoring['monitoring_id']] = baseline
    monitoring['monitoring_state'] = 'successor-next-generation-twenty-eight-renewed-baseline-active'
    monitoring['baseline_id'] = baseline['baseline_id']
    return {
        'state': 'telegram-successor-next-generation-twenty-eight-renewed-baseline-certified-active',
        'baseline': baseline,
        'monitoring': monitoring,
        'external_calls_made': 0,
        'next_layer': 'successor-next-generation-twenty-eight-renewed-baseline-continuity-expiry-renewal-governance',
    }


@router.get('/status')
def status() -> dict:
    return {
        'monitoring_records': len(_monitor_store),
        'audits': sum(len(items) for items in _audit_store.values()),
        'drifts': len(_drift_store),
        'baselines': len(_baseline_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-twenty-eight-monitoring-drift-renewed-baseline',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><body><h1>AURON v21.468</h1><p>successor-next-generation-twenty-eight monitoring, drift governance and renewed baseline certification</p><p>no Telegram API call · no provider execution · no outbound message · external_calls_made=0</p></body></html>'
