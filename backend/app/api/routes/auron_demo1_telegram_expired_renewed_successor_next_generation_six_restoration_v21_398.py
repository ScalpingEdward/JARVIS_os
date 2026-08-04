from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_six_continuity_v21_397 import (
    _continuity_store,
    _expiry_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_six_recertification_v21_396 import (
    _baseline_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.398',
    tags=['auron-demo1-telegram-expired-renewed-successor-next-generation-six-restoration'],
)

_admission_store: dict[str, dict] = {}
_restoration_store: dict[str, dict] = {}
_succession_store: dict[str, dict] = {}

_ADMIT_PHRASE = 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION SIX RECERTIFICATION'
_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SIX CONTINUITY'
_ESTABLISH_PHRASE = 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN BASELINE'


class RecertificationAdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    admission_phrase: str = Field(min_length=1, max_length=320)
    remediation_reference: str = Field(min_length=1, max_length=300)
    remediation_statement: str = Field(min_length=1, max_length=1800)


class ContinuityRestorationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    restoration_phrase: str = Field(min_length=1, max_length=320)
    observed_expired_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    restoration_reference: str = Field(min_length=1, max_length=300)


class SuccessorBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    establishment_phrase: str = Field(min_length=1, max_length=320)
    successor_next_generation_seven_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)
    succession_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_expired_renewed_successor_next_generation_six_restoration_store() -> None:
    _admission_store.clear()
    _restoration_store.clear()
    _succession_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


@router.post('/recertification/admit')
def admit_recertification(payload: RecertificationAdmissionRequest) -> dict:
    if payload.admission_phrase != _ADMIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit expired renewed successor-next-generation-six recertification admission required')
    existing = _admission_store.get(payload.continuity_id)
    if existing:
        return {'state': 'telegram-expired-renewed-successor-next-generation-six-recertification-already-admitted', 'admission': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or expiry is None:
        raise HTTPException(status_code=409, detail='Expired v21.397 baseline with immutable expiry evidence required')
    checks = {
        'continuity_expired': continuity.get('continuity_state') == 'renewed-successor-next-generation-six-baseline-expired-recertification-required',
        'expiry_state_valid': expiry.get('expiry_state') == 'renewed-successor-next-generation-six-baseline-expired',
        'expiry_immutable': expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),
        'expired_hash_consistent': expiry.get('expired_baseline_hash') == continuity.get('active_baseline_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Recertification admission blocked', 'blockers': blockers})
    data = {'continuity_id': payload.continuity_id, 'expiry_id': expiry['expiry_id'], 'expired_baseline_hash': expiry['expired_baseline_hash'], 'remediation_reference': payload.remediation_reference, 'remediation_statement': payload.remediation_statement, 'checks': checks}
    admission = {'admission_id': str(uuid4()), **data, 'admission_state': 'expired-renewed-successor-next-generation-six-recertification-admitted', 'integrity_hash': _hash(data), 'immutable': True, 'admitted_by': payload.actor, 'admitted_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _admission_store[payload.continuity_id] = admission
    return {'state': 'telegram-expired-renewed-successor-next-generation-six-recertification-admitted', 'admission': admission, 'external_calls_made': 0}


@router.post('/continuity/restore')
def restore_continuity(payload: ContinuityRestorationRequest) -> dict:
    if payload.restoration_phrase != _RESTORE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next-generation-six continuity restoration required')
    existing = _restoration_store.get(payload.continuity_id)
    if existing:
        return {'state': 'telegram-renewed-successor-next-generation-six-continuity-already-restored', 'restoration': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    admission = _admission_store.get(payload.continuity_id)
    continuity = _continuity_by_id(payload.continuity_id)
    if admission is None or continuity is None:
        raise HTTPException(status_code=409, detail='Completed recertification admission required')
    checks = {
        'admission_immutable': admission.get('immutable') is True and bool(admission.get('integrity_hash')),
        'expired_hash_matches': payload.observed_expired_baseline_hash == admission.get('expired_baseline_hash'),
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity restoration blocked', 'blockers': blockers})
    data = {'continuity_id': payload.continuity_id, 'admission_id': admission['admission_id'], 'expired_baseline_hash': admission['expired_baseline_hash'], 'control_state': payload.control_state, 'restoration_reference': payload.restoration_reference, 'checks': checks}
    restoration = {'restoration_id': str(uuid4()), **data, 'restoration_state': 'renewed-successor-next-generation-six-continuity-restored-awaiting-successor-next-generation-seven-baseline', 'integrity_hash': _hash(data), 'immutable': True, 'restored_by': payload.actor, 'restored_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _restoration_store[payload.continuity_id] = restoration
    continuity['continuity_state'] = restoration['restoration_state']
    return {'state': 'telegram-renewed-successor-next-generation-six-continuity-restored', 'restoration': restoration, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/succession/establish')
def establish_successor_baseline(payload: SuccessorBaselineRequest) -> dict:
    if payload.establishment_phrase != _ESTABLISH_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven baseline establishment required')
    existing = _succession_store.get(payload.continuity_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-seven-baseline-already-established', 'succession': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    restoration = _restoration_store.get(payload.continuity_id)
    continuity = _continuity_by_id(payload.continuity_id)
    if restoration is None or continuity is None:
        raise HTTPException(status_code=409, detail='Completed continuity restoration required')
    previous_hash = restoration['expired_baseline_hash']
    checks = {
        'restoration_complete': restoration.get('restoration_state') == 'renewed-successor-next-generation-six-continuity-restored-awaiting-successor-next-generation-seven-baseline',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'successor_hash_distinct': payload.successor_next_generation_seven_hash != previous_hash,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor baseline establishment blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {'continuity_id': payload.continuity_id, 'restoration_id': restoration['restoration_id'], 'superseded_baseline_hash': previous_hash, 'successor_next_generation_seven_hash': payload.successor_next_generation_seven_hash, 'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(), 'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(), 'succession_reference': payload.succession_reference, 'checks': checks}
    succession = {'succession_id': str(uuid4()), **data, 'succession_state': 'successor-next-generation-seven-baseline-active', 'integrity_hash': _hash(data), 'immutable': True, 'established_by': payload.actor, 'established_at': now.isoformat(), 'external_calls_made': 0}
    _succession_store[payload.continuity_id] = succession
    continuity.update(continuity_state='successor-next-generation-seven-baseline-active', active_baseline_hash=payload.successor_next_generation_seven_hash, next_health_check_due_at=data['next_health_check_due_at'], valid_until=data['valid_until'])
    baseline = _baseline_store.get(continuity.get('monitoring_id'))
    if baseline is not None:
        baseline['baseline_state'] = 'renewed-successor-next-generation-six-baseline-superseded'
        baseline['superseded_by_succession_id'] = succession['succession_id']
    return {'state': 'telegram-successor-next-generation-seven-baseline-established', 'succession': succession, 'continuity': continuity, 'superseded_baseline': baseline, 'external_calls_made': 0, 'next_layer': 'successor-next-generation-seven-stabilization-observation-certification'}


@router.get('/status')
def status() -> dict:
    return {'admissions': len(_admission_store), 'restorations': len(_restoration_store), 'successions': len(_succession_store), 'external_calls_made': 0, 'mode': 'expired-renewed-successor-next-generation-six-restoration-succession-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.398</title></head><body><h1>AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION SIX RESTORATION COMMAND CENTER</h1><p>Recertification admission, continuity restoration and successor-next-generation-seven baseline succession governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
