from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_two_recertification_v21_376 import (
    _baseline_store,
    _recertification_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_two_monitoring_v21_375 import (
    _monitoring_store,
)
from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_continuity_v21_372 import (
    _continuity_monitor_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.377',
    tags=['auron-demo1-telegram-renewed-successor-next-generation-two-continuity'],
)

_continuity_store: dict[str, dict] = {}
_health_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_validity_store: dict[str, list[dict]] = {}

_START = 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION TWO CONTINUITY'
_CHECK = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO RECERTIFICATION HEALTH'
_EXPIRE = 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION TWO BASELINE'
_RENEW = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO BASELINE VALIDITY'


class ContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)


class HealthCheckRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    statement: str = Field(min_length=1, max_length=1800)
    checked_at: datetime | None = None


class ExpiryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    expiry_phrase: str = Field(min_length=1, max_length=320)
    expiry_reference: str = Field(min_length=1, max_length=300)
    expiry_statement: str = Field(min_length=1, max_length=1800)
    expired_at: datetime | None = None


class ValidityRenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    observed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    extension_days: int = Field(default=365, ge=1, le=3650)
    renewal_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_renewed_successor_next_generation_two_continuity_store() -> None:
    _continuity_store.clear()
    _health_store.clear()
    _expiry_store.clear()
    _validity_store.clear()


def _hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _monitoring(monitoring_id: str) -> dict | None:
    return next((x for x in _monitoring_store.values() if x.get('monitoring_id') == monitoring_id), None)


def _continuity(continuity_id: str) -> dict | None:
    return next((x for x in _continuity_store.values() if x.get('continuity_id') == continuity_id), None)


@router.post('/continuity/start')
def start_continuity(payload: ContinuityStartRequest) -> dict:
    if payload.start_phrase != _START:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-two continuity approval required')
    existing = _continuity_store.get(payload.monitoring_id)
    if existing:
        return {'state': 'telegram-renewed-successor-next-generation-two-continuity-already-started', 'continuity': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring(payload.monitoring_id)
    baseline = _baseline_store.get(payload.monitoring_id)
    recertification = _recertification_store.get(payload.monitoring_id)
    if not monitoring or not baseline or not recertification:
        raise HTTPException(status_code=409, detail='Active v21.376 renewed successor-next-generation-two baseline required')
    active_hash = baseline.get('renewed_baseline_hash')
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-successor-next-generation-two-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'recertification_complete': recertification.get('recertification_state') == 'successor-next-generation-two-succession-recertified',
        'monitoring_active': monitoring.get('monitoring_state') == 'renewed-successor-next-generation-two-monitoring-active',
        'hash_consistent': bool(active_hash) and monitoring.get('active_successor_next_generation_two_hash') == active_hash,
    }
    blockers = [k for k, v in checks.items() if not v]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'monitoring_id': payload.monitoring_id,
        'baseline_id': baseline['baseline_id'],
        'recertification_id': recertification['recertification_id'],
        'active_baseline_hash': active_hash,
        'health_check_interval_days': payload.health_check_interval_days,
        'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        'checks': checks,
    }
    record = {
        'continuity_id': str(uuid4()),
        **data,
        'continuity_state': 'renewed-successor-next-generation-two-continuity-active',
        'health_check_count': 0,
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _continuity_store[payload.monitoring_id] = record
    return {'state': 'telegram-renewed-successor-next-generation-two-continuity-started', 'continuity': record, 'external_calls_made': 0}


@router.post('/health/check')
def check_health(payload: HealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK:
        raise HTTPException(status_code=403, detail='Explicit recertification health check required')
    record = _continuity(payload.continuity_id)
    if not record:
        raise HTTPException(status_code=404, detail='Renewed successor-next-generation-two continuity not found')
    if record.get('continuity_state') != 'renewed-successor-next-generation-two-continuity-active':
        raise HTTPException(status_code=409, detail='Continuity is not active')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    hash_matches = payload.observed_baseline_hash == record['active_baseline_hash']
    not_expired = checked_at < datetime.fromisoformat(record['valid_until'])
    healthy = hash_matches and not_expired and payload.control_state == 'healthy'
    checks = _health_store.setdefault(record['continuity_id'], [])
    data = {
        'continuity_id': record['continuity_id'],
        'sequence': len(checks) + 1,
        'expected_hash': record['active_baseline_hash'],
        'observed_hash': payload.observed_baseline_hash,
        'hash_matches': hash_matches,
        'not_expired': not_expired,
        'control_state': payload.control_state,
        'healthy': healthy,
        'statement': payload.statement,
    }
    evidence = {
        'health_check_id': str(uuid4()),
        **data,
        'health_state': 'recertification-health-verified' if healthy else 'recertification-health-failed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'checked_by': payload.actor,
        'checked_at': checked_at.isoformat(),
        'external_calls_made': 0,
    }
    checks.append(evidence)
    record.update(health_check_count=len(checks), last_health_check_id=evidence['health_check_id'], next_health_check_due_at=(checked_at + timedelta(days=record['health_check_interval_days'])).isoformat())
    if not healthy:
        record['continuity_state'] = 'renewed-successor-next-generation-two-continuity-review-required'
    return {'state': f"telegram-{evidence['health_state']}", 'health_check': evidence, 'continuity': record, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: ExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE:
        raise HTTPException(status_code=403, detail='Explicit baseline expiry approval required')
    record = _continuity(payload.continuity_id)
    if not record:
        raise HTTPException(status_code=404, detail='Continuity not found')
    existing = _expiry_store.get(record['continuity_id'])
    if existing:
        return {'state': 'telegram-renewed-successor-next-generation-two-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    checks = {
        'validity_elapsed': expired_at >= datetime.fromisoformat(record['valid_until']),
        'state_known': record.get('continuity_state') in {'renewed-successor-next-generation-two-continuity-active', 'renewed-successor-next-generation-two-continuity-review-required'},
        'hash_present': bool(record.get('active_baseline_hash')),
    }
    blockers = [k for k, v in checks.items() if not v]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Baseline expiry blocked', 'blockers': blockers})
    data = {'continuity_id': record['continuity_id'], 'monitoring_id': record['monitoring_id'], 'baseline_id': record['baseline_id'], 'expired_baseline_hash': record['active_baseline_hash'], 'expiry_reference': payload.expiry_reference, 'expiry_statement': payload.expiry_statement, 'checks': checks}
    expiry = {'expiry_id': str(uuid4()), **data, 'expiry_state': 'renewed-successor-next-generation-two-baseline-expired', 'integrity_hash': _hash(data), 'immutable': True, 'expired_by': payload.actor, 'expired_at': expired_at.isoformat(), 'external_calls_made': 0}
    _expiry_store[record['continuity_id']] = expiry
    record['continuity_state'] = 'renewed-successor-next-generation-two-baseline-expired-recertification-required'
    return {'state': 'telegram-renewed-successor-next-generation-two-baseline-expired', 'expiry': expiry, 'continuity': record, 'external_calls_made': 0, 'next_layer': 'expired-renewed-successor-next-generation-two-restoration-and-succession'}


@router.post('/baseline/validity/renew')
def renew_validity(payload: ValidityRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW:
        raise HTTPException(status_code=403, detail='Explicit baseline validity renewal required')
    record = _continuity(payload.continuity_id)
    if not record:
        raise HTTPException(status_code=404, detail='Continuity not found')
    if record.get('continuity_state') != 'renewed-successor-next-generation-two-continuity-active':
        raise HTTPException(status_code=409, detail='Only an active baseline can be renewed')
    now = datetime.now(timezone.utc)
    checks = {'hash_matches': payload.observed_baseline_hash == record['active_baseline_hash'], 'controls_healthy': payload.control_state == 'healthy', 'not_expired': now < datetime.fromisoformat(record['valid_until'])}
    blockers = [k for k, v in checks.items() if not v]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Validity renewal blocked', 'blockers': blockers})
    renewals = _validity_store.setdefault(record['continuity_id'], [])
    data = {'continuity_id': record['continuity_id'], 'sequence': len(renewals) + 1, 'baseline_hash': record['active_baseline_hash'], 'old_valid_until': record['valid_until'], 'new_valid_until': (now + timedelta(days=payload.extension_days)).isoformat(), 'renewal_reference': payload.renewal_reference, 'checks': checks}
    renewal = {'validity_renewal_id': str(uuid4()), **data, 'renewal_state': 'successor-next-generation-two-baseline-validity-renewed', 'integrity_hash': _hash(data), 'immutable': True, 'renewed_by': payload.actor, 'renewed_at': now.isoformat(), 'external_calls_made': 0}
    renewals.append(renewal)
    record['valid_until'] = data['new_valid_until']
    record['last_validity_renewal_id'] = renewal['validity_renewal_id']
    return {'state': 'telegram-successor-next-generation-two-baseline-validity-renewed', 'validity_renewal': renewal, 'continuity': record, 'external_calls_made': 0}


@router.get('/status')
def status() -> dict:
    return {'continuity_records': len(_continuity_store), 'health_checks': sum(map(len, _health_store.values())), 'expired_baselines': len(_expiry_store), 'validity_renewals': sum(map(len, _validity_store.values())), 'external_calls_made': 0, 'mode': 'renewed-successor-next-generation-two-continuity-health-expiry-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>AURON v21.377</title></head><body><main><h1>AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION TWO CONTINUITY COMMAND CENTER</h1><p>Periodic recertification health checks, validity renewal and baseline-expiry governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></main></body></html>'''
