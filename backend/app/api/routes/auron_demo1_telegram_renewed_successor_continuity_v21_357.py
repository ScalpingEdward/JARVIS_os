from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_recertification_v21_356 import (
    _baseline_store,
    _recertification_store,
)
from app.api.routes.auron_demo1_telegram_successor_baseline_monitoring_v21_355 import _monitoring_store

router = APIRouter(prefix='/auron/demo1/v21.357', tags=['auron-demo1-telegram-renewed-successor-continuity'])
_continuity_store: dict[str, dict] = {}
_health_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM RENEWED SUCCESSOR CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR RECERTIFICATION HEALTH'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR BASELINE'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR BASELINE VALIDITY'


class ContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    baseline_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    health_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=36500)


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
    reason: str = Field(min_length=1, max_length=1800)
    expired_at: datetime | None = None


class ValidityRenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    renewal_reference: str = Field(min_length=1, max_length=300)
    validity_days: int = Field(default=365, ge=1, le=36500)


def reset_telegram_renewed_successor_continuity_store() -> None:
    _continuity_store.clear()
    _health_store.clear()
    _expiry_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _baseline_by_id(baseline_id: str) -> dict | None:
    return next((item for item in _baseline_store.values() if item.get('baseline_id') == baseline_id), None)


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


@router.post('/continuity/start')
def start_continuity(payload: ContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor continuity approval required')
    existing = _continuity_store.get(payload.baseline_id)
    if existing:
        return {'state': 'telegram-renewed-successor-continuity-already-started', 'continuity': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    baseline = _baseline_by_id(payload.baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail='Renewed successor baseline not found')
    monitoring = next((item for item in _monitoring_store.values() if item.get('monitoring_id') == baseline.get('monitoring_id')), None)
    recertification = _recertification_store.get(baseline.get('monitoring_id'))
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-successor-assurance-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('baseline_hash')),
        'recertification_complete': bool(recertification and recertification.get('recertification_state') == 'successor-succession-recertified'),
        'monitoring_active': bool(monitoring and monitoring.get('monitoring_state') == 'certified-successor-monitoring-active'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed successor continuity blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {'baseline_id': baseline['baseline_id'], 'monitoring_id': baseline['monitoring_id'], 'active_baseline_hash': baseline['baseline_hash'], 'active_successor_hash': baseline['active_successor_hash'], 'health_interval_days': payload.health_interval_days, 'validity_days': payload.validity_days, 'next_health_due_at': (now + timedelta(days=payload.health_interval_days)).isoformat(), 'baseline_expires_at': (now + timedelta(days=payload.validity_days)).isoformat(), 'checks': checks}
    continuity = {'continuity_id': str(uuid4()), **data, 'continuity_state': 'renewed-successor-continuity-active', 'health_check_count': 0, 'integrity_hash': _hash(data), 'immutable': True, 'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0}
    _continuity_store[payload.baseline_id] = continuity
    return {'state': 'telegram-renewed-successor-continuity-started', 'continuity': continuity, 'external_calls_made': 0}


@router.post('/health/check')
def check_health(payload: HealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor recertification health check required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Renewed successor continuity not found')
    if continuity.get('continuity_state') != 'renewed-successor-continuity-active':
        raise HTTPException(status_code=409, detail='Renewed successor continuity is not active')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    hash_matches = payload.observed_baseline_hash == continuity['active_baseline_hash']
    not_expired = checked_at < datetime.fromisoformat(continuity['baseline_expires_at'])
    healthy = hash_matches and not_expired and payload.control_state == 'healthy'
    sequence = continuity['health_check_count'] + 1
    data = {'continuity_id': continuity['continuity_id'], 'sequence': sequence, 'expected_baseline_hash': continuity['active_baseline_hash'], 'observed_baseline_hash': payload.observed_baseline_hash, 'hash_matches': hash_matches, 'baseline_not_expired': not_expired, 'control_state': payload.control_state, 'healthy': healthy, 'statement': payload.statement}
    check = {'health_check_id': str(uuid4()), **data, 'health_state': 'successor-recertification-health-verified' if healthy else 'successor-recertification-health-degraded', 'integrity_hash': _hash(data), 'immutable': True, 'checked_by': payload.actor, 'checked_at': checked_at.isoformat(), 'external_calls_made': 0}
    _health_store.setdefault(continuity['continuity_id'], []).append(check)
    continuity.update(health_check_count=sequence, last_health_check_id=check['health_check_id'], next_health_due_at=(checked_at + timedelta(days=continuity['health_interval_days'])).isoformat(), continuity_state='renewed-successor-continuity-active' if healthy else 'successor-baseline-expiry-review-required')
    return {'state': f"telegram-{check['health_state']}", 'health_check': check, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: ExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor baseline expiry required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Renewed successor continuity not found')
    existing = _expiry_store.get(payload.continuity_id)
    if existing and existing.get('expiry_state') == 'renewed-successor-baseline-expired':
        return {'state': 'telegram-renewed-successor-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    latest = (_health_store.get(payload.continuity_id) or [None])[-1]
    due = expired_at >= datetime.fromisoformat(continuity['baseline_expires_at']) or bool(latest and latest.get('healthy') is False)
    if not due:
        raise HTTPException(status_code=409, detail='Baseline expiry is not due')
    data = {'continuity_id': continuity['continuity_id'], 'baseline_id': continuity['baseline_id'], 'active_baseline_hash': continuity['active_baseline_hash'], 'reason': payload.reason, 'last_health_check_id': latest.get('health_check_id') if latest else None}
    expiry = {'expiry_id': str(uuid4()), **data, 'expiry_state': 'renewed-successor-baseline-expired', 'integrity_hash': _hash(data), 'immutable': True, 'expired_by': payload.actor, 'expired_at': expired_at.isoformat(), 'external_calls_made': 0}
    _expiry_store[payload.continuity_id] = expiry
    continuity['continuity_state'] = 'renewed-successor-baseline-expired'
    return {'state': 'telegram-renewed-successor-baseline-expired', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/validity/renew')
def renew_validity(payload: ValidityRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor baseline validity renewal required')
    continuity = _continuity_by_id(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or expiry is None:
        raise HTTPException(status_code=404, detail='Expired successor baseline not found')
    latest = (_health_store.get(payload.continuity_id) or [None])[-1]
    checks = {'baseline_expired': expiry.get('expiry_state') == 'renewed-successor-baseline-expired', 'latest_health_healthy': bool(latest and latest.get('healthy') is True), 'baseline_hash_consistent': bool(latest and latest.get('observed_baseline_hash') == continuity.get('active_baseline_hash'))}
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor baseline validity renewal blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    renewed_expires_at = (now + timedelta(days=payload.validity_days)).isoformat()
    renewal_data = {'continuity_id': continuity['continuity_id'], 'expiry_id': expiry['expiry_id'], 'renewal_reference': payload.renewal_reference, 'validity_days': payload.validity_days, 'renewed_expires_at': renewed_expires_at, 'checks': checks}
    expiry.update(expiry_state='renewed-successor-baseline-validity-renewed', renewal_reference=payload.renewal_reference, renewal_integrity_hash=_hash(renewal_data), renewed_by=payload.actor, renewed_at=now.isoformat())
    continuity.update(continuity_state='renewed-successor-continuity-active', validity_days=payload.validity_days, baseline_expires_at=renewed_expires_at)
    return {'state': 'telegram-successor-baseline-validity-renewed', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'expired-successor-baseline-recertification-admission'}


@router.get('/status')
def status() -> dict:
    return {'continuity_records': len(_continuity_store), 'recertification_health_checks': sum(len(items) for items in _health_store.values()), 'expired_baselines': sum(1 for item in _expiry_store.values() if item.get('expiry_state') == 'renewed-successor-baseline-expired'), 'external_calls_made': 0, 'mode': 'renewed-successor-continuity-recertification-health-baseline-expiry-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_successor_recertification_v21_356 import command_center as previous
    return previous().replace('v21.356', 'v21.357').replace('AURON TELEGRAM SUCCESSOR RECERTIFICATION COMMAND CENTER', 'AURON TELEGRAM RENEWED SUCCESSOR CONTINUITY COMMAND CENTER')
