from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_twenty_seven_monitoring_v21_465 import (
    _baseline_store,
    _monitor_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.466',
    tags=['auron-demo1-telegram-successor-next-generation-twenty-seven-continuity'],
)

_continuity_store: dict[str, dict] = {}
_checkpoint_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_renewal_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY SEVEN BASELINE CONTINUITY'
_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY SEVEN BASELINE CONTINUITY'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY SEVEN RENEWED BASELINE'
_RENEWAL_PHRASE = 'REQUEST AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY SEVEN RENEWAL'


class ContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    baseline_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    validity_days: int = Field(default=90, ge=1, le=3650)
    checkpoint_interval_days: int = Field(default=30, ge=1, le=3650)


class ContinuityCheckpointRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_twenty_seven_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    continuity_statement: str = Field(min_length=1, max_length=1800)
    checked_at: datetime | None = None


class BaselineExpiryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    expiry_phrase: str = Field(min_length=1, max_length=320)
    expiry_reference: str = Field(min_length=1, max_length=300)
    expiry_statement: str = Field(min_length=1, max_length=1800)
    expired_at: datetime | None = None


class RenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    expiry_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    renewal_reference: str = Field(min_length=1, max_length=300)
    renewal_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_twenty_seven_continuity_store() -> None:
    _continuity_store.clear()
    _checkpoint_store.clear()
    _expiry_store.clear()
    _renewal_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _find(store: dict[str, dict], key: str, value: str) -> dict | None:
    return next((item for item in store.values() if item.get(key) == value), None)


@router.post('/continuity/start')
def start_continuity(payload: ContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-seven baseline continuity approval required')
    existing = _continuity_store.get(payload.baseline_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-seven-continuity-already-started', 'continuity': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    baseline = _find(_baseline_store, 'baseline_id', payload.baseline_id)
    if baseline is None:
        raise HTTPException(404, 'Certified successor-next-generation-twenty-seven renewed baseline not found')
    monitoring = _find(_monitor_store, 'monitoring_id', baseline['monitoring_id'])
    checks = {
        'baseline_active': baseline.get('baseline_state') == 'successor-next-generation-twenty-seven-renewed-baseline-certified-active',
        'baseline_immutable': baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'monitoring_baseline_active': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-twenty-seven-renewed-baseline-active',
        'hash_aligned': monitoring is not None and monitoring.get('active_successor_next_generation_twenty_seven_hash') == baseline.get('active_successor_next_generation_twenty_seven_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Continuity start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'baseline_id': baseline['baseline_id'],
        'monitoring_id': baseline['monitoring_id'],
        'active_successor_next_generation_twenty_seven_hash': baseline['active_successor_next_generation_twenty_seven_hash'],
        'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'checkpoint_interval_days': payload.checkpoint_interval_days,
        'next_checkpoint_due_at': (now + timedelta(days=payload.checkpoint_interval_days)).isoformat(),
        'checks': checks,
    }
    continuity = {
        'continuity_id': str(uuid4()), **data,
        'continuity_state': 'successor-next-generation-twenty-seven-renewed-baseline-continuity-active',
        'integrity_hash': _hash(data), 'immutable': True,
        'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0,
    }
    _continuity_store[payload.baseline_id] = continuity
    return {'state': 'telegram-successor-next-generation-twenty-seven-renewed-baseline-continuity-started', 'continuity': continuity, 'external_calls_made': 0}


@router.post('/continuity/checkpoint')
def check_continuity(payload: ContinuityCheckpointRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-seven continuity check required')
    continuity = _find(_continuity_store, 'continuity_id', payload.continuity_id)
    if continuity is None:
        raise HTTPException(404, 'Successor-next-generation-twenty-seven continuity not found')
    if continuity.get('continuity_state') != 'successor-next-generation-twenty-seven-renewed-baseline-continuity-active':
        raise HTTPException(409, 'Active successor-next-generation-twenty-seven continuity required')
    checked_at = payload.checked_at or datetime.now(timezone.utc)
    expected = continuity['active_successor_next_generation_twenty_seven_hash']
    hash_matches = payload.observed_successor_next_generation_twenty_seven_hash == expected
    within_validity = checked_at <= datetime.fromisoformat(continuity['valid_until'])
    healthy = hash_matches and within_validity and payload.control_state == 'healthy'
    checkpoints = _checkpoint_store.setdefault(continuity['continuity_id'], [])
    data = {
        'continuity_id': continuity['continuity_id'], 'sequence': len(checkpoints) + 1,
        'expected_hash': expected, 'observed_hash': payload.observed_successor_next_generation_twenty_seven_hash,
        'hash_matches': hash_matches, 'within_validity': within_validity,
        'control_state': payload.control_state, 'healthy': healthy,
        'continuity_statement': payload.continuity_statement,
    }
    checkpoint = {
        'checkpoint_id': str(uuid4()), **data,
        'checkpoint_state': 'successor-next-generation-twenty-seven-continuity-passed' if healthy else 'successor-next-generation-twenty-seven-continuity-failed',
        'integrity_hash': _hash(data), 'immutable': True,
        'checked_by': payload.actor, 'checked_at': checked_at.isoformat(), 'external_calls_made': 0,
    }
    checkpoints.append(checkpoint)
    if healthy:
        continuity['next_checkpoint_due_at'] = (checked_at + timedelta(days=continuity['checkpoint_interval_days'])).isoformat()
    else:
        continuity['continuity_state'] = 'successor-next-generation-twenty-seven-baseline-expiry-required' if not within_validity else 'successor-next-generation-twenty-seven-continuity-broken'
        continuity['failed_checkpoint_id'] = checkpoint['checkpoint_id']
    return {'state': f"telegram-{checkpoint['checkpoint_state']}", 'checkpoint': checkpoint, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/expire')
def expire_baseline(payload: BaselineExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-seven renewed baseline expiry required')
    continuity = _find(_continuity_store, 'continuity_id', payload.continuity_id)
    if continuity is None:
        raise HTTPException(404, 'Successor-next-generation-twenty-seven continuity not found')
    existing = _expiry_store.get(continuity['continuity_id'])
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-seven-baseline-already-expired', 'expiry': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    expired_at = payload.expired_at or datetime.now(timezone.utc)
    validity_elapsed = expired_at >= datetime.fromisoformat(continuity['valid_until'])
    broken = continuity.get('continuity_state') in {
        'successor-next-generation-twenty-seven-baseline-expiry-required',
        'successor-next-generation-twenty-seven-continuity-broken',
    }
    checks = {
        'expiry_due_or_broken': validity_elapsed or broken,
        'continuity_immutable': continuity.get('immutable') is True and bool(continuity.get('integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-seven baseline expiry blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'], 'baseline_id': continuity['baseline_id'],
        'monitoring_id': continuity['monitoring_id'], 'expiry_reference': payload.expiry_reference,
        'expiry_statement': payload.expiry_statement, 'checks': checks,
    }
    expiry = {
        'expiry_id': str(uuid4()), **data,
        'expiry_state': 'successor-next-generation-twenty-seven-renewed-baseline-expired',
        'integrity_hash': _hash(data), 'immutable': True,
        'expired_by': payload.actor, 'expired_at': expired_at.isoformat(), 'external_calls_made': 0,
    }
    _expiry_store[continuity['continuity_id']] = expiry
    continuity['continuity_state'] = 'successor-next-generation-twenty-seven-renewed-baseline-expired'
    continuity['expiry_id'] = expiry['expiry_id']
    baseline = _find(_baseline_store, 'baseline_id', continuity['baseline_id'])
    monitoring = _find(_monitor_store, 'monitoring_id', continuity['monitoring_id'])
    if baseline is not None:
        baseline['baseline_state'] = 'successor-next-generation-twenty-seven-renewed-baseline-expired'
        baseline['expiry_id'] = expiry['expiry_id']
    if monitoring is not None:
        monitoring['monitoring_state'] = 'successor-next-generation-twenty-seven-renewal-required'
        monitoring['expiry_id'] = expiry['expiry_id']
    return {'state': 'telegram-successor-next-generation-twenty-seven-renewed-baseline-expired', 'expiry': expiry, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/renewal/request')
def request_renewal(payload: RenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEWAL_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-seven renewal request required')
    expiry = _find(_expiry_store, 'expiry_id', payload.expiry_id)
    if expiry is None:
        raise HTTPException(404, 'Immutable successor-next-generation-twenty-seven expiry not found')
    existing = _renewal_store.get(payload.expiry_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-seven-renewal-already-requested', 'renewal': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _find(_monitor_store, 'monitoring_id', expiry['monitoring_id'])
    checks = {
        'expiry_final': expiry.get('expiry_state') == 'successor-next-generation-twenty-seven-renewed-baseline-expired',
        'expiry_immutable': expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),
        'monitoring_requires_renewal': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-twenty-seven-renewal-required',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-seven renewal request blocked', 'blockers': blockers})
    data = {
        'expiry_id': expiry['expiry_id'], 'continuity_id': expiry['continuity_id'],
        'baseline_id': expiry['baseline_id'], 'monitoring_id': expiry['monitoring_id'],
        'renewal_reference': payload.renewal_reference,
        'renewal_statement': payload.renewal_statement, 'checks': checks,
    }
    renewal = {
        'renewal_request_id': str(uuid4()), **data,
        'renewal_state': 'successor-next-generation-twenty-seven-renewal-requested',
        'integrity_hash': _hash(data), 'immutable': True,
        'requested_by': payload.actor, 'requested_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _renewal_store[payload.expiry_id] = renewal
    return {
        'state': 'telegram-successor-next-generation-twenty-seven-renewal-requested',
        'renewal': renewal, 'external_calls_made': 0,
        'next_layer': 'successor-next-generation-twenty-eight-restoration-controlled-activation-succession-governance',
    }


@router.get('/status')
def status() -> dict:
    return {
        'continuities': len(_continuity_store),
        'checkpoints': sum(len(items) for items in _checkpoint_store.values()),
        'expiries': len(_expiry_store),
        'renewals': len(_renewal_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-twenty-seven-continuity-expiry-renewal',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><body><h1>AURON v21.466</h1><p>successor-next-generation-twenty-seven continuity, expiry and renewal governance</p><p>no Telegram API call · no provider execution · no outbound message · external_calls_made=0</p></body></html>'
