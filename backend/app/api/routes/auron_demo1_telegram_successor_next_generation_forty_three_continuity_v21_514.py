from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_three_monitoring_v21_513 import _baseline_store, _drift_store, _monitor_store

router = APIRouter(prefix='/auron/demo1/v21.514', tags=['auron-demo1-telegram-successor-next-generation-forty-three-continuity'])

_continuity_store: dict[str, list[dict]] = {}
_expiry_store: dict[str, dict] = {}
_renewal_store: dict[str, dict] = {}

_CHECK_PHRASE = 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY THREE CONTINUITY'
_EXPIRE_PHRASE = 'EXPIRE AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY THREE BASELINE'
_RENEW_PHRASE = 'REQUEST AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY THREE RENEWAL'

class ContinuityCheckRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    check_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_forty_three_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    validity_days: int = Field(default=90, ge=1, le=3650)
    continuity_statement: str = Field(min_length=1, max_length=1800)

class ExpiryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    expiry_phrase: str = Field(min_length=1, max_length=320)
    expiry_reference: str = Field(min_length=1, max_length=300)
    expiry_statement: str = Field(min_length=1, max_length=1800)

class RenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    renewal_reference: str = Field(min_length=1, max_length=300)
    renewal_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_forty_three_continuity_store() -> None:
    _continuity_store.clear(); _expiry_store.clear(); _renewal_store.clear()


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _find(store: dict[str, dict], key: str, value: str) -> dict | None:
    return next((item for item in store.values() if item.get(key) == value), None)


@router.post('/continuity/check')
def check_continuity(payload: ContinuityCheckRequest) -> dict:
    if payload.check_phrase != _CHECK_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-forty-three continuity check required')
    monitoring = _find(_monitor_store, 'monitoring_id', payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(404, 'Successor-next-generation-forty-three monitoring not found')
    baseline = _baseline_store.get(monitoring['monitoring_id'])
    drift = _drift_store.get(monitoring['monitoring_id'])
    expected = monitoring.get('active_successor_next_generation_forty_three_hash')
    checks = {
        'renewed_baseline_active': baseline is not None and baseline.get('baseline_state') == 'successor-next-generation-forty-three-renewed-baseline-certified-active',
        'baseline_immutable': baseline is not None and baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),
        'monitoring_baseline_active': monitoring.get('monitoring_state') == 'successor-next-generation-forty-three-renewed-baseline-active',
        'no_open_drift': drift is None,
        'hash_matches': payload.observed_successor_next_generation_forty_three_hash == expected,
        'controls_healthy': payload.control_state == 'healthy',
    }
    healthy = all(checks.values())
    now = datetime.now(timezone.utc)
    data = {'monitoring_id':monitoring['monitoring_id'],'baseline_id':baseline.get('baseline_id') if baseline else None,'expected_hash':expected,'observed_hash':payload.observed_successor_next_generation_forty_three_hash,'control_state':payload.control_state,'validity_days':payload.validity_days,'valid_until':(now+timedelta(days=payload.validity_days)).isoformat() if healthy else now.isoformat(),'continuity_statement':payload.continuity_statement,'checks':checks}
    checkpoint = {'checkpoint_id':str(uuid4()),**data,'continuity_state':'successor-next-generation-forty-three-continuity-healthy' if healthy else 'successor-next-generation-forty-three-continuity-broken','integrity_hash':_hash(data),'immutable':True,'checked_by':payload.actor,'checked_at':now.isoformat(),'external_calls_made':0}
    _continuity_store.setdefault(monitoring['monitoring_id'], []).append(checkpoint)
    monitoring['monitoring_state'] = 'successor-next-generation-forty-three-continuity-active' if healthy else 'successor-next-generation-forty-three-continuity-broken'
    monitoring['latest_continuity_checkpoint_id'] = checkpoint['checkpoint_id']
    monitoring['valid_until'] = checkpoint['valid_until']
    return {'state':f"telegram-{checkpoint['continuity_state']}",'checkpoint':checkpoint,'monitoring':monitoring,'external_calls_made':0}


@router.post('/baseline/expire')
def expire_baseline(payload: ExpiryRequest) -> dict:
    if payload.expiry_phrase != _EXPIRE_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-forty-three baseline expiry approval required')
    monitoring = _find(_monitor_store, 'monitoring_id', payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(404, 'Successor-next-generation-forty-three monitoring not found')
    existing = _expiry_store.get(monitoring['monitoring_id'])
    if existing:
        return {'state':'telegram-successor-next-generation-forty-three-baseline-already-expired','expiry':existing,'idempotent_replay':True,'external_calls_made':0}
    baseline = _baseline_store.get(monitoring['monitoring_id'])
    checkpoints = _continuity_store.get(monitoring['monitoring_id'], [])
    latest = checkpoints[-1] if checkpoints else None
    now = datetime.now(timezone.utc)
    valid_until = datetime.fromisoformat(latest['valid_until']) if latest and latest.get('valid_until') else None
    checks = {'baseline_exists':baseline is not None,'baseline_immutable':baseline is not None and baseline.get('immutable') is True and bool(baseline.get('integrity_hash')),'continuity_checkpoint_exists':latest is not None,'expiry_condition_met':latest is not None and (latest.get('continuity_state') == 'successor-next-generation-forty-three-continuity-broken' or (valid_until is not None and now >= valid_until))}
    blockers = [k for k,v in checks.items() if not v]
    if blockers:
        raise HTTPException(409, {'message':'Successor-next-generation-forty-three baseline expiry blocked','blockers':blockers})
    data = {'monitoring_id':monitoring['monitoring_id'],'baseline_id':baseline['baseline_id'],'checkpoint_id':latest['checkpoint_id'],'expiry_reference':payload.expiry_reference,'expiry_statement':payload.expiry_statement,'checks':checks}
    expiry = {'expiry_id':str(uuid4()),**data,'expiry_state':'successor-next-generation-forty-three-baseline-expired-controlled','integrity_hash':_hash(data),'immutable':True,'expired_by':payload.actor,'expired_at':now.isoformat(),'external_calls_made':0}
    _expiry_store[monitoring['monitoring_id']] = expiry
    baseline['baseline_state'] = 'successor-next-generation-forty-three-renewed-baseline-expired'
    monitoring['monitoring_state'] = 'successor-next-generation-forty-three-renewal-required'
    monitoring['expiry_id'] = expiry['expiry_id']
    return {'state':'telegram-successor-next-generation-forty-three-baseline-expired-controlled','expiry':expiry,'monitoring':monitoring,'external_calls_made':0}


@router.post('/renewal/request')
def request_renewal(payload: RenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-forty-three renewal request required')
    monitoring = _find(_monitor_store, 'monitoring_id', payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(404, 'Successor-next-generation-forty-three monitoring not found')
    existing = _renewal_store.get(monitoring['monitoring_id'])
    if existing:
        return {'state':'telegram-successor-next-generation-forty-three-renewal-already-requested','renewal':existing,'idempotent_replay':True,'external_calls_made':0}
    expiry = _expiry_store.get(monitoring['monitoring_id']); baseline = _baseline_store.get(monitoring['monitoring_id'])
    checks = {'renewal_required':monitoring.get('monitoring_state')=='successor-next-generation-forty-three-renewal-required','controlled_expiry_exists':expiry is not None and expiry.get('expiry_state')=='successor-next-generation-forty-three-baseline-expired-controlled','expiry_immutable':expiry is not None and expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),'baseline_expired':baseline is not None and baseline.get('baseline_state')=='successor-next-generation-forty-three-renewed-baseline-expired'}
    blockers = [k for k,v in checks.items() if not v]
    if blockers:
        raise HTTPException(409, {'message':'Successor-next-generation-forty-three renewal request blocked','blockers':blockers})
    data = {'monitoring_id':monitoring['monitoring_id'],'baseline_id':baseline['baseline_id'],'expiry_id':expiry['expiry_id'],'renewal_reference':payload.renewal_reference,'renewal_statement':payload.renewal_statement,'checks':checks}
    renewal = {'renewal_request_id':str(uuid4()),**data,'renewal_state':'successor-next-generation-forty-three-renewal-requested','integrity_hash':_hash(data),'immutable':True,'requested_by':payload.actor,'requested_at':datetime.now(timezone.utc).isoformat(),'external_calls_made':0}
    _renewal_store[monitoring['monitoring_id']] = renewal
    monitoring['monitoring_state'] = 'successor-next-generation-forty-three-renewal-requested'; monitoring['renewal_request_id'] = renewal['renewal_request_id']
    return {'state':'telegram-successor-next-generation-forty-three-renewal-requested','renewal':renewal,'monitoring':monitoring,'external_calls_made':0,'next_layer':'successor-next-generation-forty-four-restoration-controlled-activation-succession-governance'}


@router.get('/status')
def status() -> dict:
    return {'continuity_checkpoints':sum(len(v) for v in _continuity_store.values()),'expiries':len(_expiry_store),'renewal_requests':len(_renewal_store),'external_calls_made':0,'mode':'successor-next-generation-forty-three-continuity-expiry-renewal'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><body><h1>AURON v21.514</h1><p>successor-next-generation-forty-three renewed baseline continuity, expiry and renewal governance</p><p>no Telegram API call · no provider execution · no outbound message · external_calls_made=0</p></body></html>'
