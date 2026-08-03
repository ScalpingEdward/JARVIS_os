from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_assurance_recertification_v21_351 import (
    _baseline_store,
    _recertification_store,
)
from app.api.routes.auron_demo1_telegram_certified_reclosure_assurance_v21_350 import _assurance_store

router = APIRouter(prefix='/auron/demo1/v21.352', tags=['auron-demo1-telegram-renewed-assurance-continuity'])

_continuity_store: dict[str, dict] = {}
_health_check_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM RENEWED ASSURANCE CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM RECERTIFICATION HEALTH'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM RENEWED ASSURANCE BASELINE'
_RENEW_EXPIRY_PHRASE = 'RENEW AURON TELEGRAM BASELINE EXPIRY WINDOW'


class RenewedAssuranceContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    baseline_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    baseline_validity_days: int = Field(default=365, ge=1, le=36500)


class RecertificationHealthCheckRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    check_statement: str = Field(min_length=1, max_length=1800)
    checked_at: datetime | None = None


class BaselineExpiryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    expiry_phrase: str = Field(min_length=1, max_length=320)
    expiry_reason: str = Field(min_length=1, max_length=1800)
    expired_at: datetime | None = None


class BaselineExpiryRenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    renewal_reference: str = Field(min_length=1, max_length=300)
    baseline_validity_days: int = Field(default=365, ge=1, le=36500)


def reset_telegram_renewed_assurance_continuity_store() -> None:
    _continuity_store.clear()
    _health_check_store.clear()
    _expiry_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _baseline_by_id(baseline_id: str) -> dict | None:
    return next((item for item in _baseline_store.values() if item.get('baseline_id') == baseline_id), None)


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


@router.post('/continuity/start')
def start_renewed_assurance_continuity(payload: RenewedAssuranceContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed assurance continuity approval required')
    existing = _continuity_store.get(payload.baseline_id)
    if existing is not None:
        return {'state': 'telegram-renewed-assurance-continuity-already-started', 'continuity': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    baseline = _baseline_by_id(payload.baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail='Renewed assurance baseline not found')
    assurance = next((item for item in _assurance_store.values() if item.get('assurance_id') == baseline.get('assurance_id')), None)
    recertification = _recertification_store.get(baseline.get('assurance_id'))
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'renewed-assurance-baseline-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('baseline_hash')),
        'recertification_complete': bool(recertification and recertification.get('recertification_state') == 'certified-reclosure-assurance-recertified'),
        'assurance_active': bool(assurance and assurance.get('assurance_state') == 'certified-reclosure-long-term-assurance-active'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed assurance continuity blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'baseline_id': baseline['baseline_id'],
        'assurance_id': baseline['assurance_id'],
        'recertification_id': baseline['recertification_id'],
        'active_baseline_hash': baseline['baseline_hash'],
        'health_check_interval_days': payload.health_check_interval_days,
        'baseline_validity_days': payload.baseline_validity_days,
        'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        'baseline_expires_at': (now + timedelta(days=payload.baseline_validity_days)).isoformat(),
        'checks': checks,
    }
    continuity = {
        'continuity_id': str(uuid4()),
        **data,
        'continuity_state': 'renewed-assurance-continuity-active',
        'integrity_hash': _hash(data),
        'health_check_count': 0,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _continuity_store[payload.baseline_id] = continuity
    return {'state': 'telegram-renewed-assurance-continuity-started', 'continuity': continuity, 'external_calls_made': 0}


@router.post('/health/check')
def check_recertification_health(payload: RecertificationHealthCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit recertification health check approval required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Renewed assurance continuity not found')
    if continuity.get('continuity_state') != 'renewed-assurance-continuity-active':
        raise HTTPException(status_code=409, detail='Renewed assurance continuity is not active')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    not_expired = checked_at < datetime.fromisoformat(continuity['baseline_expires_at'])
    hash_matches = payload.observed_baseline_hash == continuity['active_baseline_hash']
    healthy = not_expired and hash_matches and payload.control_state == 'healthy'
    sequence = continuity['health_check_count'] + 1
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'sequence': sequence,
        'expected_baseline_hash': continuity['active_baseline_hash'],
        'observed_baseline_hash': payload.observed_baseline_hash,
        'hash_matches': hash_matches,
        'baseline_not_expired': not_expired,
        'control_state': payload.control_state,
        'healthy': healthy,
        'check_statement': payload.check_statement,
    }
    check = {
        'health_check_id': str(uuid4()),
        **data,
        'health_state': 'recertification-health-verified' if healthy else 'recertification-health-degraded',
        'integrity_hash': _hash(data),
        'immutable': True,
        'checked_by': payload.actor,
        'checked_at': checked_at.isoformat(),
        'external_calls_made': 0,
    }
    _health_check_store.setdefault(continuity['continuity_id'], []).append(check)
    continuity.update(
        health_check_count=sequence,
        last_health_check_id=check['health_check_id'],
        last_checked_at=checked_at.isoformat(),
        next_health_check_due_at=(checked_at + timedelta(days=continuity['health_check_interval_days'])).isoformat(),
        continuity_state='renewed-assurance-continuity-active' if healthy else 'baseline-expiry-or-recertification-review-required',
    )
    return {'state': f"telegram-{check['health_state']}", 'health_check': check, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_renewed_assurance_baseline(payload: BaselineExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed assurance baseline expiry approval required')
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Renewed assurance continuity not found')
    existing = _expiry_store.get(continuity['continuity_id'])
    if existing and existing.get('expiry_state') == 'renewed-assurance-baseline-expired':
        return {'state': 'telegram-renewed-assurance-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    latest = (_health_check_store.get(continuity['continuity_id']) or [None])[-1]
    checks = {
        'expiry_due_or_health_failed': expired_at >= datetime.fromisoformat(continuity['baseline_expires_at']) or bool(latest and latest.get('healthy') is False),
        'continuity_not_already_expired': continuity.get('continuity_state') != 'renewed-assurance-baseline-expired',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Baseline expiry blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'active_baseline_hash': continuity['active_baseline_hash'],
        'expiry_reason': payload.expiry_reason,
        'last_health_check_id': latest.get('health_check_id') if latest else None,
        'checks': checks,
    }
    expiry = {
        'expiry_id': str(uuid4()),
        **data,
        'expiry_state': 'renewed-assurance-baseline-expired',
        'integrity_hash': _hash(data),
        'immutable': True,
        'expired_by': payload.actor,
        'expired_at': expired_at.isoformat(),
        'external_calls_made': 0,
    }
    _expiry_store[continuity['continuity_id']] = expiry
    continuity['continuity_state'] = 'renewed-assurance-baseline-expired'
    return {'state': 'telegram-renewed-assurance-baseline-expired', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expiry-window/renew')
def renew_baseline_expiry_window(payload: BaselineExpiryRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_EXPIRY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit baseline expiry-window renewal required')
    continuity = _continuity_by_id(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or expiry is None:
        raise HTTPException(status_code=404, detail='Expired renewed assurance baseline not found')
    latest = (_health_check_store.get(continuity['continuity_id']) or [None])[-1]
    checks = {
        'baseline_expired': expiry.get('expiry_state') == 'renewed-assurance-baseline-expired',
        'latest_health_check_healthy': bool(latest and latest.get('healthy') is True),
        'baseline_hash_consistent': bool(latest and latest.get('observed_baseline_hash') == continuity.get('active_baseline_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Baseline expiry-window renewal blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    renewal_data = {
        'continuity_id': continuity['continuity_id'],
        'expiry_id': expiry['expiry_id'],
        'renewal_reference': payload.renewal_reference,
        'baseline_validity_days': payload.baseline_validity_days,
        'renewed_expires_at': (now + timedelta(days=payload.baseline_validity_days)).isoformat(),
        'checks': checks,
    }
    expiry.update(
        expiry_state='renewed-assurance-baseline-expiry-window-renewed',
        renewal_reference=payload.renewal_reference,
        renewal_integrity_hash=_hash(renewal_data),
        renewed_by=payload.actor,
        renewed_at=now.isoformat(),
    )
    continuity.update(
        continuity_state='renewed-assurance-continuity-active',
        baseline_validity_days=payload.baseline_validity_days,
        baseline_expires_at=renewal_data['renewed_expires_at'],
    )
    return {'state': 'telegram-renewed-assurance-baseline-expiry-window-renewed', 'expiry': expiry, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'renewed-assurance-expiry-recertification-governance'}


@router.get('/status')
def renewed_assurance_continuity_status() -> dict:
    return {
        'continuity_records': len(_continuity_store),
        'recertification_health_checks': sum(len(items) for items in _health_check_store.values()),
        'expired_baselines': sum(1 for item in _expiry_store.values() if item.get('expiry_state') == 'renewed-assurance-baseline-expired'),
        'renewed_expiry_windows': sum(1 for item in _expiry_store.values() if item.get('expiry_state') == 'renewed-assurance-baseline-expiry-window-renewed'),
        'external_calls_made': 0,
        'mode': 'renewed-assurance-continuity-recertification-health-baseline-expiry-governance',
    }


@router.get('/continuities')
def list_continuities() -> dict:
    return {'count': len(_continuity_store), 'items': list(_continuity_store.values()), 'external_calls_made': 0}


@router.get('/health-checks')
def list_health_checks() -> dict:
    items = [item for checks in _health_check_store.values() for item in checks]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/expiries')
def list_expiries() -> dict:
    return {'count': len(_expiry_store), 'items': list(_expiry_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_assurance_recertification_v21_351 import command_center as v21_351_command_center
    return v21_351_command_center().replace('v21.351', 'v21.352').replace(
        'AURON TELEGRAM ASSURANCE RECERTIFICATION COMMAND CENTER',
        'AURON TELEGRAM RENEWED ASSURANCE CONTINUITY COMMAND CENTER',
    )
