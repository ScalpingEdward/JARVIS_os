from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_three_recertification_v21_381 import _baseline_store
from app.api.routes.auron_demo1_telegram_successor_next_generation_three_monitoring_v21_380 import _monitoring_store

router = APIRouter(prefix='/auron/demo1/v21.382', tags=['auron-demo1-telegram-renewed-successor-next-generation-three-continuity'])

_continuity_store: dict[str, dict] = {}
_health_check_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_renewal_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION THREE CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE RECERTIFICATION HEALTH'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION THREE BASELINE'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE BASELINE VALIDITY'


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
    reason: str = Field(min_length=1, max_length=1800)
    expired_at: datetime | None = None


class ValidityRenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    extension_days: int = Field(default=365, ge=1, le=3650)
    renewal_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_renewed_successor_next_generation_three_continuity_store() -> None:
    _continuity_store.clear(); _health_check_store.clear(); _expiry_store.clear(); _renewal_store.clear()


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


@router.post('/continuity/start')
def start_continuity(payload: ContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-three continuity approval required')
    if payload.monitoring_id in _continuity_store:
        return {'state': 'telegram-renewed-successor-next-generation-three-continuity-already-started', 'continuity': _continuity_store[payload.monitoring_id], 'idempotent_replay': True, 'external_calls_made': 0}
    baseline = _baseline_store.get(payload.monitoring_id)
    monitoring = next((item for item in _monitoring_store.values() if item.get('monitoring_id') == payload.monitoring_id), None)
    if baseline is None or monitoring is None:
        raise HTTPException(status_code=409, detail='Active v21.381 renewed baseline required')
    active_hash = baseline.get('renewed_successor_next_generation_three_hash')
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-successor-next-generation-three-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'monitoring_active': monitoring.get('monitoring_state') == 'renewed-successor-next-generation-three-monitoring-active',
        'hash_consistent': bool(active_hash) and active_hash == monitoring.get('active_successor_next_generation_three_hash'),
    }
    blockers = [k for k, v in checks.items() if not v]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {'monitoring_id': payload.monitoring_id, 'baseline_id': baseline['baseline_id'], 'active_baseline_hash': active_hash, 'health_check_interval_days': payload.health_check_interval_days, 'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(), 'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(), 'checks': checks}
    continuity = {'continuity_id': str(uuid4()), **data, 'continuity_state': 'renewed-successor-next-generation-three-continuity-active', 'health_check_count': 0, 'integrity_hash': _hash(data), 'immutable': True, 'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0}
    _continuity_store[payload.monitoring_id] = continuity
    return {'state': 'telegram-renewed-successor-next-generation-three-continuity-started', 'continuity': continuity, 'external_calls_made': 0}


@router.post('/health/check')
def check_health(payload: HealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit recertification health check required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    hash_matches = payload.observed_baseline_hash == continuity['active_baseline_hash']
    not_expired = checked_at < datetime.fromisoformat(continuity['valid_until'])
    healthy = hash_matches and not_expired and payload.control_state == 'healthy'
    checks = _health_check_store.setdefault(continuity['continuity_id'], [])
    data = {'continuity_id': continuity['continuity_id'], 'sequence': len(checks) + 1, 'expected_hash': continuity['active_baseline_hash'], 'observed_hash': payload.observed_baseline_hash, 'hash_matches': hash_matches, 'not_expired': not_expired, 'control_state': payload.control_state, 'healthy': healthy, 'statement': payload.statement}
    evidence = {'health_check_id': str(uuid4()), **data, 'health_check_state': 'renewed-successor-next-generation-three-health-verified' if healthy else 'renewed-successor-next-generation-three-health-failed-expiry-review-required', 'integrity_hash': _hash(data), 'immutable': True, 'checked_by': payload.actor, 'checked_at': checked_at.isoformat(), 'external_calls_made': 0}
    checks.append(evidence)
    continuity.update(health_check_count=len(checks), last_health_check_id=evidence['health_check_id'], next_health_check_due_at=(checked_at + timedelta(days=continuity['health_check_interval_days'])).isoformat(), continuity_state='renewed-successor-next-generation-three-continuity-active' if healthy else 'renewed-successor-next-generation-three-baseline-expiry-review-required')
    return {'state': f"telegram-{evidence['health_check_state']}", 'health_check': evidence, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: ExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit baseline expiry approval required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    if continuity['continuity_id'] in _expiry_store:
        return {'state': 'telegram-renewed-successor-next-generation-three-baseline-already-expired', 'expiry': _expiry_store[continuity['continuity_id']], 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    naturally_expired = expired_at >= datetime.fromisoformat(continuity['valid_until'])
    unhealthy = continuity.get('continuity_state') == 'renewed-successor-next-generation-three-baseline-expiry-review-required'
    if not (naturally_expired or unhealthy):
        raise HTTPException(status_code=409, detail='Healthy unexpired baseline cannot be expired')
    data = {'continuity_id': continuity['continuity_id'], 'monitoring_id': continuity['monitoring_id'], 'expired_baseline_hash': continuity['active_baseline_hash'], 'naturally_expired': naturally_expired, 'unhealthy_evidence_present': unhealthy, 'reason': payload.reason}
    expiry = {'expiry_id': str(uuid4()), **data, 'expiry_state': 'renewed-successor-next-generation-three-baseline-expired', 'integrity_hash': _hash(data), 'immutable': True, 'expired_by': payload.actor, 'expired_at': expired_at.isoformat(), 'external_calls_made': 0}
    _expiry_store[continuity['continuity_id']] = expiry
    continuity['continuity_state'] = 'renewed-successor-next-generation-three-baseline-expired-recertification-required'
    return {'state': 'telegram-renewed-successor-next-generation-three-baseline-expired', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/renew-validity')
def renew_validity(payload: ValidityRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit baseline validity renewal required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    if continuity['continuity_id'] in _renewal_store:
        return {'state': 'telegram-successor-next-generation-three-validity-already-renewed', 'renewal': _renewal_store[continuity['continuity_id']], 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc)
    latest = (_health_check_store.get(continuity['continuity_id']) or [None])[-1]
    checks = {'continuity_active': continuity.get('continuity_state') == 'renewed-successor-next-generation-three-continuity-active', 'baseline_unexpired': now < datetime.fromisoformat(continuity['valid_until']), 'latest_check_healthy': latest is not None and latest.get('healthy') is True, 'hash_consistent': latest is not None and latest.get('observed_hash') == continuity['active_baseline_hash']}
    blockers = [k for k, v in checks.items() if not v]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Validity renewal blocked', 'blockers': blockers})
    previous_valid_until = continuity['valid_until']
    new_valid_until = (datetime.fromisoformat(previous_valid_until) + timedelta(days=payload.extension_days)).isoformat()
    data = {'continuity_id': continuity['continuity_id'], 'previous_valid_until': previous_valid_until, 'new_valid_until': new_valid_until, 'extension_days': payload.extension_days, 'renewal_reference': payload.renewal_reference, 'checks': checks}
    renewal = {'renewal_id': str(uuid4()), **data, 'renewal_state': 'successor-next-generation-three-baseline-validity-renewed', 'integrity_hash': _hash(data), 'immutable': True, 'renewed_by': payload.actor, 'renewed_at': now.isoformat(), 'external_calls_made': 0}
    _renewal_store[continuity['continuity_id']] = renewal
    continuity['valid_until'] = new_valid_until
    return {'state': 'telegram-successor-next-generation-three-baseline-validity-renewed', 'renewal': renewal, 'continuity': continuity, 'external_calls_made': 0}


@router.get('/status')
def status() -> dict:
    return {'continuity_records': len(_continuity_store), 'health_checks': sum(len(items) for items in _health_check_store.values()), 'baseline_expiries': len(_expiry_store), 'validity_renewals': len(_renewal_store), 'external_calls_made': 0, 'mode': 'renewed-successor-next-generation-three-continuity-health-expiry-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.382</title></head><body><h1>AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION THREE CONTINUITY COMMAND CENTER</h1><p>Periodic recertification health checks and baseline-expiry governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
