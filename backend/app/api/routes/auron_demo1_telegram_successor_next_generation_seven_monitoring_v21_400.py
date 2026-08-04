from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_seven_stabilization_v21_399 import (
    _certification_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.400',
    tags=['auron-demo1-telegram-successor-next-generation-seven-monitoring'],
)

_monitoring_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_resolution_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION SEVEN MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN HEALTH'
_OPEN_DRIFT_PHRASE = 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN DRIFT'
_RESOLVE_DRIFT_PHRASE = 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN DRIFT'


class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)


class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_seven_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    audit_reference: str = Field(min_length=1, max_length=300)
    audit_statement: str = Field(min_length=1, max_length=1800)


class DriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    trigger_audit_id: str = Field(min_length=1, max_length=160)
    open_phrase: str = Field(min_length=1, max_length=320)
    remediation_reference: str = Field(min_length=1, max_length=300)


class DriftResolutionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    drift_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    corrected_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    resolution_reference: str = Field(min_length=1, max_length=300)
    resolution_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_seven_monitoring_store() -> None:
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


def _drift_by_id(drift_id: str) -> dict | None:
    return next((item for item in _drift_store.values() if item.get('drift_id') == drift_id), None)


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified successor-next-generation-seven monitoring approval required')
    existing = _monitoring_store.get(payload.certification_id)
    if existing is not None:
        return {'state': 'telegram-certified-successor-next-generation-seven-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certification = _certification_by_id(payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=409, detail='Stable v21.399 succession certification required')
    checks = {
        'certification_stable': certification.get('certification_state') == 'successor-next-generation-seven-succession-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'active_hash_present': bool(certification.get('active_successor_next_generation_seven_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Monitoring start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'certification_id': certification['certification_id'],
        'active_successor_next_generation_seven_hash': certification['active_successor_next_generation_seven_hash'],
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    monitoring = {
        'monitoring_id': str(uuid4()),
        **data,
        'monitoring_state': 'certified-successor-next-generation-seven-monitoring-active',
        'open_drift_id': None,
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _monitoring_store[payload.certification_id] = monitoring
    return {'state': 'telegram-certified-successor-next-generation-seven-monitoring-started', 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/health/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven health audit required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    if monitoring.get('open_drift_id'):
        raise HTTPException(status_code=409, detail='Open successor-next-generation-seven drift blocks routine health audits')
    expected_hash = monitoring['active_successor_next_generation_seven_hash']
    hash_matches = payload.observed_successor_next_generation_seven_hash == expected_hash
    healthy = hash_matches and payload.continuity_state == 'healthy'
    audits = _audit_store.setdefault(monitoring['monitoring_id'], [])
    now = datetime.now(timezone.utc)
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'sequence': len(audits) + 1,
        'expected_hash': expected_hash,
        'observed_hash': payload.observed_successor_next_generation_seven_hash,
        'hash_matches': hash_matches,
        'continuity_state': payload.continuity_state,
        'healthy': healthy,
        'audit_reference': payload.audit_reference,
        'audit_statement': payload.audit_statement,
    }
    audit = {
        'audit_id': str(uuid4()),
        **data,
        'audit_state': 'successor-next-generation-seven-health-audit-passed' if healthy else 'successor-next-generation-seven-health-audit-failed-drift-required',
        'integrity_hash': _hash(data),
        'immutable': True,
        'audited_by': payload.actor,
        'audited_at': now.isoformat(),
        'external_calls_made': 0,
    }
    audits.append(audit)
    monitoring['next_audit_due_at'] = (now + timedelta(days=monitoring['audit_interval_days'])).isoformat()
    if not healthy:
        monitoring['monitoring_state'] = 'successor-next-generation-seven-drift-detected'
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/open')
def open_drift(payload: DriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven drift opening required')
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Monitoring not found')
    if monitoring.get('open_drift_id'):
        existing = _drift_by_id(monitoring['open_drift_id'])
        return {'state': 'telegram-successor-next-generation-seven-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    trigger = next((item for item in _audit_store.get(monitoring['monitoring_id'], []) if item.get('audit_id') == payload.trigger_audit_id), None)
    if trigger is None or trigger.get('healthy') is not False:
        raise HTTPException(status_code=409, detail='Failed immutable trigger audit required')
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'trigger_audit_id': trigger['audit_id'],
        'expected_hash': trigger['expected_hash'],
        'observed_hash': trigger['observed_hash'],
        'remediation_reference': payload.remediation_reference,
    }
    drift = {
        'drift_id': str(uuid4()),
        **data,
        'drift_state': 'successor-next-generation-seven-drift-open',
        'integrity_hash': _hash(data),
        'immutable': True,
        'opened_by': payload.actor,
        'opened_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _drift_store[monitoring['monitoring_id']] = drift
    monitoring['open_drift_id'] = drift['drift_id']
    monitoring['monitoring_state'] = 'successor-next-generation-seven-drift-open-remediation-required'
    return {'state': 'telegram-successor-next-generation-seven-drift-open', 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/drift/resolve')
def resolve_drift(payload: DriftResolutionRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven drift resolution required')
    drift = _drift_by_id(payload.drift_id)
    if drift is None:
        raise HTTPException(status_code=404, detail='Open drift not found')
    existing = _resolution_store.get(drift['drift_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-seven-drift-already-resolved', 'resolution': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(drift['monitoring_id'])
    checks = {
        'drift_open': drift.get('drift_state') == 'successor-next-generation-seven-drift-open',
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
        'corrected_hash_matches': monitoring is not None and payload.corrected_hash == monitoring.get('active_successor_next_generation_seven_hash'),
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Drift resolution blocked', 'blockers': blockers})
    data = {
        'drift_id': drift['drift_id'],
        'monitoring_id': drift['monitoring_id'],
        'corrected_hash': payload.corrected_hash,
        'control_state': payload.control_state,
        'resolution_reference': payload.resolution_reference,
        'resolution_statement': payload.resolution_statement,
        'checks': checks,
    }
    resolution = {
        'resolution_id': str(uuid4()),
        **data,
        'resolution_state': 'successor-next-generation-seven-drift-resolved',
        'integrity_hash': _hash(data),
        'immutable': True,
        'resolved_by': payload.actor,
        'resolved_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _resolution_store[drift['drift_id']] = resolution
    drift['drift_state'] = 'successor-next-generation-seven-drift-resolved'
    monitoring['open_drift_id'] = None
    monitoring['monitoring_state'] = 'successor-next-generation-seven-drift-resolved-recertification-required'
    return {'state': 'telegram-successor-next-generation-seven-drift-resolved', 'resolution': resolution, 'drift': drift, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'successor-next-generation-seven-remediation-validation-recertification-renewed-baseline-governance'}


@router.get('/status')
def status() -> dict:
    return {
        'monitoring_sessions': len(_monitoring_store),
        'audits': sum(len(items) for items in _audit_store.values()),
        'drifts': len(_drift_store),
        'resolutions': len(_resolution_store),
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-seven-monitoring-audit-drift-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.400</title></head><body><h1>AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN MONITORING COMMAND CENTER</h1><p>Long-term health audit and drift governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
