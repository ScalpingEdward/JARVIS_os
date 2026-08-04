from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_seven_recertification_v21_401 import (
    _baseline_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.402',
    tags=['auron-demo1-telegram-renewed-successor-next-generation-seven-continuity'],
)

_continuity_store: dict[str, dict] = {}
_health_check_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_validity_renewal_store: dict[str, list[dict]] = {}

_START_PHRASE = 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SEVEN CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN RECERTIFICATION HEALTH'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SEVEN BASELINE'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN BASELINE VALIDITY'


class ContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    baseline_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)


class HealthCheckRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_seven_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern='^[0-9a-f]{64}$',
    )
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    health_statement: str = Field(min_length=1, max_length=1800)
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
    observed_successor_next_generation_seven_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern='^[0-9a-f]{64}$',
    )
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    validity_extension_days: int = Field(default=365, ge=1, le=3650)
    renewal_reference: str = Field(min_length=1, max_length=300)
    renewed_at: datetime | None = None


def reset_telegram_renewed_successor_next_generation_seven_continuity_store() -> None:
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
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-seven continuity approval required')
    existing = _continuity_store.get(payload.baseline_id)
    if existing is not None:
        return {
            'state': 'telegram-renewed-successor-next-generation-seven-continuity-already-started',
            'continuity': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }
    baseline = _baseline_by_id(payload.baseline_id)
    if baseline is None:
        raise HTTPException(status_code=409, detail='Active v21.401 renewed successor-next-generation-seven baseline required')
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-successor-next-generation-seven-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'renewed_hash_present': bool(baseline.get('renewed_successor_next_generation_seven_hash')),
        'valid_until_present': bool(baseline.get('valid_until')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'baseline_id': baseline['baseline_id'],
        'renewed_successor_next_generation_seven_hash': baseline['renewed_successor_next_generation_seven_hash'],
        'health_check_interval_days': payload.health_check_interval_days,
        'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        'valid_until': baseline['valid_until'],
        'checks': checks,
    }
    continuity = {
        'continuity_id': str(uuid4()),
        **data,
        'continuity_state': 'renewed-successor-next-generation-seven-continuity-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _continuity_store[payload.baseline_id] = continuity
    return {'state': 'telegram-renewed-successor-next-generation-seven-continuity-started', 'continuity': continuity, 'external_calls_made': 0}


@router.post('/health/check')
def check_health(payload: HealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven recertification health check required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    if continuity.get('continuity_state') != 'renewed-successor-next-generation-seven-continuity-active':
        raise HTTPException(status_code=409, detail='Active unexpired continuity required')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    valid_until = datetime.fromisoformat(continuity['valid_until'])
    expected_hash = continuity['renewed_successor_next_generation_seven_hash']
    hash_matches = payload.observed_successor_next_generation_seven_hash == expected_hash
    unexpired = checked_at < valid_until
    healthy = hash_matches and unexpired and payload.control_state == 'healthy'
    checks = _health_check_store.setdefault(continuity['continuity_id'], [])
    data = {
        'continuity_id': continuity['continuity_id'],
        'sequence': len(checks) + 1,
        'expected_hash': expected_hash,
        'observed_hash': payload.observed_successor_next_generation_seven_hash,
        'hash_matches': hash_matches,
        'control_state': payload.control_state,
        'unexpired': unexpired,
        'healthy': healthy,
        'health_statement': payload.health_statement,
    }
    health_check = {
        'health_check_id': str(uuid4()),
        **data,
        'health_state': 'successor-next-generation-seven-recertification-healthy' if healthy else 'successor-next-generation-seven-recertification-failed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'checked_by': payload.actor,
        'checked_at': checked_at.isoformat(),
        'external_calls_made': 0,
    }
    checks.append(health_check)
    if healthy:
        continuity['next_health_check_due_at'] = (checked_at + timedelta(days=continuity['health_check_interval_days'])).isoformat()
    else:
        continuity['continuity_state'] = 'renewed-successor-next-generation-seven-continuity-degraded'
    return {'state': f"telegram-{health_check['health_state']}", 'health_check': health_check, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: BaselineExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-seven baseline expiry required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    existing = _expiry_store.get(continuity['continuity_id'])
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-seven-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    valid_until = datetime.fromisoformat(continuity['valid_until'])
    if expired_at < valid_until:
        raise HTTPException(status_code=409, detail='Baseline validity has not elapsed')
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'expired_hash': continuity['renewed_successor_next_generation_seven_hash'],
        'valid_until': continuity['valid_until'],
        'expiry_reference': payload.expiry_reference,
        'expiry_statement': payload.expiry_statement,
    }
    expiry = {
        'expiry_id': str(uuid4()),
        **data,
        'expiry_state': 'renewed-successor-next-generation-seven-baseline-expired',
        'integrity_hash': _hash(data),
        'immutable': True,
        'expired_by': payload.actor,
        'expired_at': expired_at.isoformat(),
        'external_calls_made': 0,
    }
    _expiry_store[continuity['continuity_id']] = expiry
    continuity['continuity_state'] = 'renewed-successor-next-generation-seven-baseline-expired'
    continuity['expiry_id'] = expiry['expiry_id']
    return {'state': 'telegram-renewed-successor-next-generation-seven-baseline-expired', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/validity/renew')
def renew_validity(payload: ValidityRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven baseline-validity renewal required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Continuity not found')
    if continuity.get('continuity_state') != 'renewed-successor-next-generation-seven-continuity-active':
        raise HTTPException(status_code=409, detail='Healthy active continuity required')
    renewed_at = payload.renewed_at or datetime.now(timezone.utc)
    current_valid_until = datetime.fromisoformat(continuity['valid_until'])
    expected_hash = continuity['renewed_successor_next_generation_seven_hash']
    checks = {
        'hash_matches': payload.observed_successor_next_generation_seven_hash == expected_hash,
        'controls_healthy': payload.control_state == 'healthy',
        'baseline_unexpired': renewed_at < current_valid_until,
        'no_expiry_evidence': continuity['continuity_id'] not in _expiry_store,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Validity renewal blocked', 'blockers': blockers})
    new_valid_until = current_valid_until + timedelta(days=payload.validity_extension_days)
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'active_hash': expected_hash,
        'previous_valid_until': continuity['valid_until'],
        'new_valid_until': new_valid_until.isoformat(),
        'validity_extension_days': payload.validity_extension_days,
        'renewal_reference': payload.renewal_reference,
        'checks': checks,
    }
    renewal = {
        'validity_renewal_id': str(uuid4()),
        **data,
        'renewal_state': 'successor-next-generation-seven-baseline-validity-renewed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': renewed_at.isoformat(),
        'external_calls_made': 0,
    }
    _validity_renewal_store.setdefault(continuity['continuity_id'], []).append(renewal)
    continuity['valid_until'] = new_valid_until.isoformat()
    return {'state': 'telegram-successor-next-generation-seven-baseline-validity-renewed', 'renewal': renewal, 'continuity': continuity, 'external_calls_made': 0}


@router.get('/status')
def status() -> dict:
    return {
        'continuities': len(_continuity_store),
        'health_checks': sum(len(items) for items in _health_check_store.values()),
        'expiries': len(_expiry_store),
        'validity_renewals': sum(len(items) for items in _validity_renewal_store.values()),
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-seven-continuity-health-expiry-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.402</title></head><body><h1>AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SEVEN CONTINUITY COMMAND CENTER</h1><p>Periodic recertification health checks and baseline-expiry governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
