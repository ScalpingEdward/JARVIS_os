from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_recertification_v21_371 import (
    _baseline_store,
    _recertification_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_monitoring_v21_370 import (
    _monitoring_store,
)
from app.api.routes.auron_demo1_telegram_renewed_successor_next_continuity_v21_367 import (
    _continuity_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.372',
    tags=['auron-demo1-telegram-renewed-successor-next-generation-continuity'],
)
_continuity_monitor_store: dict[str, dict] = {}
_health_check_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_validity_renewal_store: dict[str, list[dict]] = {}

_START_PHRASE = 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION RECERTIFICATION HEALTH'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION BASELINE'
_RENEW_VALIDITY_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION BASELINE VALIDITY'


class ContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)


class HealthCheckRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_monitor_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    statement: str = Field(min_length=1, max_length=1800)
    checked_at: datetime | None = None


class BaselineExpiryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_monitor_id: str = Field(min_length=1, max_length=160)
    expiry_phrase: str = Field(min_length=1, max_length=320)
    expiry_reference: str = Field(min_length=1, max_length=300)
    expiry_statement: str = Field(min_length=1, max_length=1800)
    expired_at: datetime | None = None


class ValidityRenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_monitor_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    observed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    extension_days: int = Field(default=365, ge=1, le=3650)
    renewal_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_renewed_successor_next_generation_continuity_store() -> None:
    _continuity_monitor_store.clear()
    _health_check_store.clear()
    _expiry_store.clear()
    _validity_renewal_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _record_by_id(continuity_monitor_id: str) -> dict | None:
    return next((item for item in _continuity_monitor_store.values() if item.get('continuity_monitor_id') == continuity_monitor_id), None)


@router.post('/continuity/start')
def start_continuity(payload: ContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation continuity approval required')
    existing = _continuity_monitor_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-continuity-already-started', 'continuity_monitor': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    baseline = _baseline_store.get(payload.monitoring_id)
    recertification = _recertification_store.get(payload.monitoring_id)
    if monitoring is None or baseline is None or recertification is None:
        raise HTTPException(status_code=409, detail='Active v21.371 renewed successor-next-generation baseline required')
    continuity = _continuity_by_id(monitoring['continuity_id'])
    active_hash = baseline.get('renewed_baseline_hash')
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-successor-next-generation-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'recertification_complete': recertification.get('recertification_state') == 'successor-next-generation-succession-recertified',
        'monitoring_active': monitoring.get('monitoring_state') == 'renewed-successor-next-generation-monitoring-active',
        'hash_consistent': bool(active_hash) and monitoring.get('active_successor_next_generation_hash') == active_hash,
        'continuity_consistent': continuity is not None and continuity.get('active_baseline_hash') == active_hash,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed successor-next-generation continuity blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'monitoring_id': payload.monitoring_id,
        'continuity_id': monitoring['continuity_id'],
        'baseline_id': baseline['baseline_id'],
        'recertification_id': recertification['recertification_id'],
        'active_baseline_hash': active_hash,
        'health_check_interval_days': payload.health_check_interval_days,
        'validity_days': payload.validity_days,
        'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'checks': checks,
    }
    record = {
        'continuity_monitor_id': str(uuid4()), **data,
        'continuity_state': 'renewed-successor-next-generation-continuity-active',
        'health_check_count': 0,
        'integrity_hash': _hash(data), 'immutable': True,
        'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0,
    }
    _continuity_monitor_store[payload.monitoring_id] = record
    return {'state': 'telegram-renewed-successor-next-generation-continuity-started', 'continuity_monitor': record, 'external_calls_made': 0}


@router.post('/health/check')
def check_health(payload: HealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation recertification health check required')
    record = _record_by_id(payload.continuity_monitor_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Renewed successor-next-generation continuity record not found')
    if record.get('continuity_state') != 'renewed-successor-next-generation-continuity-active':
        raise HTTPException(status_code=409, detail='Renewed successor-next-generation continuity is not active')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    expected_hash = record['active_baseline_hash']
    hash_matches = payload.observed_baseline_hash == expected_hash
    not_expired = checked_at < datetime.fromisoformat(record['valid_until'])
    healthy = hash_matches and not_expired and payload.control_state == 'healthy'
    checks = _health_check_store.setdefault(record['continuity_monitor_id'], [])
    data = {
        'continuity_monitor_id': record['continuity_monitor_id'], 'sequence': len(checks) + 1,
        'expected_baseline_hash': expected_hash, 'observed_baseline_hash': payload.observed_baseline_hash,
        'hash_matches': hash_matches, 'not_expired': not_expired,
        'control_state': payload.control_state, 'healthy': healthy, 'statement': payload.statement,
    }
    evidence = {
        'health_check_id': str(uuid4()), **data,
        'health_state': 'recertification-health-verified' if healthy else 'recertification-health-failed',
        'integrity_hash': _hash(data), 'immutable': True,
        'checked_by': payload.actor, 'checked_at': checked_at.isoformat(), 'external_calls_made': 0,
    }
    checks.append(evidence)
    record.update(
        health_check_count=len(checks), last_health_check_id=evidence['health_check_id'],
        next_health_check_due_at=(checked_at + timedelta(days=record['health_check_interval_days'])).isoformat(),
    )
    if not healthy:
        record['continuity_state'] = 'renewed-successor-next-generation-continuity-review-required'
    return {'state': f"telegram-{evidence['health_state']}", 'health_check': evidence, 'continuity_monitor': record, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: BaselineExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation baseline expiry required')
    record = _record_by_id(payload.continuity_monitor_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Renewed successor-next-generation continuity record not found')
    existing = _expiry_store.get(record['continuity_monitor_id'])
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    checks = {
        'validity_elapsed': expired_at >= datetime.fromisoformat(record['valid_until']),
        'continuity_known': record.get('continuity_state') in {'renewed-successor-next-generation-continuity-active', 'renewed-successor-next-generation-continuity-review-required'},
        'baseline_hash_present': bool(record.get('active_baseline_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Baseline expiry blocked', 'blockers': blockers})
    data = {
        'continuity_monitor_id': record['continuity_monitor_id'], 'monitoring_id': record['monitoring_id'],
        'baseline_id': record['baseline_id'], 'expired_baseline_hash': record['active_baseline_hash'],
        'expiry_reference': payload.expiry_reference, 'expiry_statement': payload.expiry_statement,
        'checks': checks,
    }
    expiry = {
        'expiry_id': str(uuid4()), **data,
        'expiry_state': 'renewed-successor-next-generation-baseline-expired',
        'integrity_hash': _hash(data), 'immutable': True,
        'expired_by': payload.actor, 'expired_at': expired_at.isoformat(), 'external_calls_made': 0,
    }
    _expiry_store[record['continuity_monitor_id']] = expiry
    record['continuity_state'] = 'renewed-successor-next-generation-baseline-expired-recertification-required'
    return {'state': 'telegram-renewed-successor-next-generation-baseline-expired', 'expiry': expiry, 'continuity_monitor': record, 'external_calls_made': 0, 'next_layer': 'expired-renewed-successor-next-generation-restoration-and-succession'}


@router.post('/baseline/validity/renew')
def renew_validity(payload: ValidityRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_VALIDITY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation baseline validity renewal required')
    record = _record_by_id(payload.continuity_monitor_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Renewed successor-next-generation continuity record not found')
    if record.get('continuity_state') != 'renewed-successor-next-generation-continuity-active':
        raise HTTPException(status_code=409, detail='Only an active non-expired baseline can have validity renewed')
    now = datetime.now(timezone.utc)
    checks = {
        'hash_matches': payload.observed_baseline_hash == record['active_baseline_hash'],
        'controls_healthy': payload.control_state == 'healthy',
        'not_expired': now < datetime.fromisoformat(record['valid_until']),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Baseline validity renewal blocked', 'blockers': blockers})
    renewals = _validity_renewal_store.setdefault(record['continuity_monitor_id'], [])
    old_valid_until = record['valid_until']
    new_valid_until = (now + timedelta(days=payload.extension_days)).isoformat()
    data = {
        'continuity_monitor_id': record['continuity_monitor_id'], 'sequence': len(renewals) + 1,
        'baseline_hash': record['active_baseline_hash'], 'old_valid_until': old_valid_until,
        'new_valid_until': new_valid_until, 'renewal_reference': payload.renewal_reference,
        'checks': checks,
    }
    renewal = {
        'validity_renewal_id': str(uuid4()), **data,
        'renewal_state': 'successor-next-generation-baseline-validity-renewed',
        'integrity_hash': _hash(data), 'immutable': True,
        'renewed_by': payload.actor, 'renewed_at': now.isoformat(), 'external_calls_made': 0,
    }
    renewals.append(renewal)
    record['valid_until'] = new_valid_until
    record['last_validity_renewal_id'] = renewal['validity_renewal_id']
    return {'state': 'telegram-successor-next-generation-baseline-validity-renewed', 'validity_renewal': renewal, 'continuity_monitor': record, 'external_calls_made': 0}


@router.get('/status')
def status() -> dict:
    return {
        'continuity_monitors': len(_continuity_monitor_store),
        'health_checks': sum(len(items) for items in _health_check_store.values()),
        'expired_baselines': len(_expiry_store),
        'validity_renewals': sum(len(items) for items in _validity_renewal_store.values()),
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-continuity-health-check-baseline-expiry-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_successor_next_generation_recertification_v21_371 import command_center as previous

    html = previous().replace('v21.371', 'v21.372')
    title = 'AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION CONTINUITY COMMAND CENTER'
    if '<body>' in html:
        return html.replace('<body>', f'<body><h1>{title}</h1>', 1)
    return f'<h1>{title}</h1>{html}'
