from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_six_recertification_v21_396 import (
    _baseline_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.397',
    tags=['auron-demo1-telegram-renewed-successor-next-generation-six-continuity'],
)

_continuity_store: dict[str, dict] = {}
_health_check_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_validity_renewal_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SIX CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX RECERTIFICATION HEALTH'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SIX BASELINE'
_RENEW_VALIDITY_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX BASELINE VALIDITY'


class ContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    baseline_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)


class RecertificationHealthCheckRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_renewed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    statement: str = Field(min_length=1, max_length=1800)
    checked_at: datetime | None = None


class BaselineExpiryRequest(BaseModel):
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
    observed_renewed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    validity_days: int = Field(default=365, ge=1, le=3650)
    renewal_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_renewed_successor_next_generation_six_continuity_store() -> None:
    _continuity_store.clear()
    _health_check_store.clear()
    _expiry_store.clear()
    _validity_renewal_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _baseline_by_id(baseline_id: str) -> dict | None:
    return next((item for item in _baseline_store.values() if item.get('baseline_id') == baseline_id), None)


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


@router.post('/continuity/start')
def start_continuity(payload: ContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-six continuity approval required')
    existing = _continuity_store.get(payload.baseline_id)
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-six-continuity-already-started', 'continuity': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    baseline = _baseline_by_id(payload.baseline_id)
    if baseline is None:
        raise HTTPException(status_code=409, detail='Active v21.396 renewed successor-next-generation-six baseline required')
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-successor-next-generation-six-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'active_hash_present': bool(baseline.get('renewed_successor_next_generation_six_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'baseline_id': baseline['baseline_id'],
        'monitoring_id': baseline['monitoring_id'],
        'active_baseline_hash': baseline['renewed_successor_next_generation_six_hash'],
        'health_check_interval_days': payload.health_check_interval_days,
        'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'checks': checks,
    }
    continuity = {
        'continuity_id': str(uuid4()),
        **data,
        'continuity_state': 'renewed-successor-next-generation-six-continuity-active',
        'health_check_count': 0,
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _continuity_store[baseline['baseline_id']] = continuity
    return {'state': 'telegram-renewed-successor-next-generation-six-continuity-started', 'continuity': continuity, 'external_calls_made': 0}


@router.post('/recertification/health-check')
def check_recertification_health(payload: RecertificationHealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-six recertification health check required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    if continuity.get('continuity_state') == 'renewed-successor-next-generation-six-baseline-expired-recertification-required':
        raise HTTPException(status_code=409, detail='Expired renewed baseline blocks routine health checks')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    expired = checked_at >= datetime.fromisoformat(continuity['valid_until'])
    hash_matches = payload.observed_renewed_baseline_hash == continuity['active_baseline_hash']
    healthy = hash_matches and payload.control_state == 'healthy' and not expired
    checks = _health_check_store.setdefault(continuity['continuity_id'], [])
    data = {
        'continuity_id': continuity['continuity_id'],
        'sequence': len(checks) + 1,
        'expected_hash': continuity['active_baseline_hash'],
        'observed_hash': payload.observed_renewed_baseline_hash,
        'hash_matches': hash_matches,
        'control_state': payload.control_state,
        'validity_expired': expired,
        'healthy': healthy,
        'statement': payload.statement,
    }
    health_check = {
        'health_check_id': str(uuid4()),
        **data,
        'health_check_state': 'renewed-successor-next-generation-six-health-verified' if healthy else 'renewed-successor-next-generation-six-health-failed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'checked_by': payload.actor,
        'checked_at': checked_at.isoformat(),
        'external_calls_made': 0,
    }
    checks.append(health_check)
    continuity.update(
        health_check_count=len(checks),
        last_health_check_id=health_check['health_check_id'],
        next_health_check_due_at=(checked_at + timedelta(days=continuity['health_check_interval_days'])).isoformat(),
        continuity_state='renewed-successor-next-generation-six-continuity-active' if healthy else 'renewed-successor-next-generation-six-baseline-expiry-review-required',
    )
    return {'state': f"telegram-{health_check['health_check_state']}", 'health_check': health_check, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: BaselineExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-six baseline expiry required')
    existing = _expiry_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-six-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    validity_elapsed = expired_at >= datetime.fromisoformat(continuity['valid_until'])
    unhealthy_check = any(not item.get('healthy') for item in _health_check_store.get(continuity['continuity_id'], []))
    if not (validity_elapsed or unhealthy_check):
        raise HTTPException(status_code=409, detail='Baseline remains healthy and unexpired')
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'expired_baseline_hash': continuity['active_baseline_hash'],
        'validity_elapsed': validity_elapsed,
        'unhealthy_check_present': unhealthy_check,
        'expiry_reference': payload.expiry_reference,
        'expiry_statement': payload.expiry_statement,
    }
    expiry = {
        'expiry_id': str(uuid4()),
        **data,
        'expiry_state': 'renewed-successor-next-generation-six-baseline-expired',
        'integrity_hash': _hash(data),
        'immutable': True,
        'expired_by': payload.actor,
        'expired_at': expired_at.isoformat(),
        'external_calls_made': 0,
    }
    _expiry_store[continuity['continuity_id']] = expiry
    continuity['continuity_state'] = 'renewed-successor-next-generation-six-baseline-expired-recertification-required'
    return {'state': 'telegram-renewed-successor-next-generation-six-baseline-expired', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/validity/renew')
def renew_validity(payload: ValidityRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_VALIDITY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-six baseline validity renewal required')
    existing = _validity_renewal_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-six-validity-already-renewed', 'renewal': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    now = datetime.now(timezone.utc)
    checks = {
        'not_expired': continuity.get('continuity_state') != 'renewed-successor-next-generation-six-baseline-expired-recertification-required' and now < datetime.fromisoformat(continuity['valid_until']),
        'hash_matches': payload.observed_renewed_baseline_hash == continuity['active_baseline_hash'],
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Validity renewal blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'baseline_hash': continuity['active_baseline_hash'],
        'previous_valid_until': continuity['valid_until'],
        'renewed_valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'renewal_reference': payload.renewal_reference,
        'checks': checks,
    }
    renewal = {
        'renewal_id': str(uuid4()),
        **data,
        'renewal_state': 'renewed-successor-next-generation-six-validity-extended',
        'integrity_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _validity_renewal_store[continuity['continuity_id']] = renewal
    continuity.update(valid_until=data['renewed_valid_until'], continuity_state='renewed-successor-next-generation-six-continuity-active')
    return {'state': 'telegram-successor-next-generation-six-baseline-validity-renewed', 'renewal': renewal, 'continuity': continuity, 'external_calls_made': 0}


@router.get('/status')
def status() -> dict:
    return {
        'continuities': len(_continuity_store),
        'health_checks': sum(len(items) for items in _health_check_store.values()),
        'expiries': len(_expiry_store),
        'validity_renewals': len(_validity_renewal_store),
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-six-continuity-health-expiry-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.397</title></head><body><h1>AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SIX CONTINUITY COMMAND CENTER</h1><p>Periodic recertification health checks and baseline-expiry governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
