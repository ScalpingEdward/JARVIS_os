from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_renewed_next_successor_continuity_v21_362 import (
    _continuity_store,
    _expiry_store,
)
from app.api.routes.auron_demo1_telegram_next_successor_recertification_v21_361 import _baseline_store
from app.api.routes.auron_demo1_telegram_next_successor_monitoring_v21_360 import _monitoring_store

router = APIRouter(prefix='/auron/demo1/v21.363', tags=['auron-demo1-telegram-expired-renewed-next-successor-restoration'])
_admission_store: dict[str, dict] = {}
_restoration_store: dict[str, dict] = {}
_succession_store: dict[str, dict] = {}
_ADMIT_PHRASE = 'ADMIT AURON TELEGRAM EXPIRED RENEWED NEXT SUCCESSOR RECERTIFICATION'
_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM RENEWED NEXT SUCCESSOR CONTINUITY'
_SUCCEED_PHRASE = 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT BASELINE'


class RecertificationAdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    admission_phrase: str = Field(min_length=1, max_length=320)
    admission_reference: str = Field(min_length=1, max_length=300)
    remediation_statement: str = Field(min_length=1, max_length=1800)


class ContinuityRestorationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    restoration_phrase: str = Field(min_length=1, max_length=320)
    observed_expired_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    restoration_reference: str = Field(min_length=1, max_length=300)
    restoration_statement: str = Field(min_length=1, max_length=1800)


class SuccessorNextBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    succession_phrase: str = Field(min_length=1, max_length=320)
    successor_reference: str = Field(min_length=1, max_length=300)
    successor_next_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    validity_days: int = Field(default=365, ge=1, le=36500)
    health_interval_days: int = Field(default=30, ge=1, le=3650)


def reset_telegram_expired_renewed_next_successor_restoration_store() -> None:
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
        raise HTTPException(status_code=403, detail='Explicit expired renewed next-successor recertification admission required')
    existing = _admission_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-expired-renewed-next-successor-recertification-already-admitted', 'admission': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or expiry is None:
        raise HTTPException(status_code=404, detail='Expired renewed next-successor baseline not found')
    baseline = next((item for item in _baseline_store.values() if item.get('baseline_id') == continuity.get('baseline_id')), None)
    monitoring = next((item for item in _monitoring_store.values() if item.get('monitoring_id') == continuity.get('monitoring_id')), None)
    checks = {
        'baseline_expired': expiry.get('expiry_state') == 'renewed-next-successor-baseline-expired',
        'expiry_immutable': expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),
        'continuity_expired': continuity.get('continuity_state') == 'renewed-next-successor-baseline-expired',
        'baseline_present': baseline is not None and baseline.get('immutable') is True,
        'monitoring_present': monitoring is not None,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Expired renewed next-successor admission blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'monitoring_id': continuity['monitoring_id'],
        'expiry_id': expiry['expiry_id'],
        'expired_baseline_hash': continuity['active_baseline_hash'],
        'admission_reference': payload.admission_reference,
        'remediation_statement': payload.remediation_statement,
        'checks': checks,
    }
    admission = {
        'admission_id': str(uuid4()),
        **data,
        'admission_state': 'expired-renewed-next-successor-recertification-admitted',
        'integrity_hash': _hash(data),
        'immutable': True,
        'admitted_by': payload.actor,
        'admitted_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _admission_store[payload.continuity_id] = admission
    continuity['continuity_state'] = 'expired-renewed-next-successor-restoration-admitted'
    return {'state': 'telegram-expired-renewed-next-successor-recertification-admitted', 'admission': admission, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/continuity/restore')
def restore_continuity(payload: ContinuityRestorationRequest) -> dict:
    if payload.restoration_phrase != _RESTORE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed next-successor continuity restoration required')
    existing = _restoration_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-renewed-next-successor-continuity-already-restored', 'restoration': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    admission = _admission_store.get(payload.continuity_id)
    if continuity is None or admission is None:
        raise HTTPException(status_code=409, detail='Recertification admission required before continuity restoration')
    checks = {
        'admission_complete': admission.get('admission_state') == 'expired-renewed-next-successor-recertification-admitted',
        'admission_immutable': admission.get('immutable') is True and bool(admission.get('integrity_hash')),
        'expired_hash_verified': payload.observed_expired_baseline_hash == continuity.get('active_baseline_hash'),
        'controls_healthy': payload.control_state == 'healthy',
        'continuity_admitted': continuity.get('continuity_state') == 'expired-renewed-next-successor-restoration-admitted',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed next-successor continuity restoration blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'],
        'admission_id': admission['admission_id'],
        'verified_expired_baseline_hash': payload.observed_expired_baseline_hash,
        'control_state': payload.control_state,
        'restoration_reference': payload.restoration_reference,
        'restoration_statement': payload.restoration_statement,
        'checks': checks,
    }
    restoration = {
        'restoration_id': str(uuid4()),
        **data,
        'restoration_state': 'renewed-next-successor-continuity-restored-awaiting-successor-next-baseline',
        'integrity_hash': _hash(data),
        'immutable': True,
        'restored_by': payload.actor,
        'restored_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _restoration_store[payload.continuity_id] = restoration
    continuity['continuity_state'] = 'renewed-next-successor-restored-awaiting-successor-next-baseline'
    return {'state': 'telegram-renewed-next-successor-continuity-restored', 'restoration': restoration, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/succeed')
def establish_successor_next_baseline(payload: SuccessorNextBaselineRequest) -> dict:
    if payload.succession_phrase != _SUCCEED_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next baseline approval required')
    existing = _succession_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-baseline-already-established', 'succession': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    restoration = _restoration_store.get(payload.continuity_id)
    admission = _admission_store.get(payload.continuity_id)
    if continuity is None or restoration is None or admission is None:
        raise HTTPException(status_code=409, detail='Completed continuity restoration required before successor-next baseline')
    checks = {
        'restoration_complete': restoration.get('restoration_state') == 'renewed-next-successor-continuity-restored-awaiting-successor-next-baseline',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'admission_immutable': admission.get('immutable') is True and bool(admission.get('integrity_hash')),
        'next_hash_differs': payload.successor_next_hash != continuity.get('active_baseline_hash'),
        'continuity_awaiting_successor': continuity.get('continuity_state') == 'renewed-next-successor-restored-awaiting-successor-next-baseline',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-next baseline blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'continuity_id': continuity['continuity_id'],
        'restoration_id': restoration['restoration_id'],
        'superseded_baseline_id': continuity['baseline_id'],
        'superseded_baseline_hash': continuity['active_baseline_hash'],
        'successor_next_hash': payload.successor_next_hash,
        'successor_reference': payload.successor_reference,
        'validity_days': payload.validity_days,
        'health_interval_days': payload.health_interval_days,
        'checks': checks,
    }
    succession = {
        'succession_id': str(uuid4()),
        **data,
        'succession_state': 'successor-next-baseline-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'established_by': payload.actor,
        'established_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _succession_store[payload.continuity_id] = succession
    expiry = _expiry_store.get(payload.continuity_id)
    if expiry is not None:
        expiry.update(expiry_state='renewed-next-successor-expired-baseline-superseded', succession_id=succession['succession_id'])
    continuity.update(
        continuity_state='renewed-next-successor-continuity-active',
        superseded_baseline_id=continuity['baseline_id'],
        superseded_baseline_hash=continuity['active_baseline_hash'],
        active_baseline_hash=payload.successor_next_hash,
        successor_next_id=succession['succession_id'],
        health_interval_days=payload.health_interval_days,
        health_check_count=0,
        next_health_due_at=(now + timedelta(days=payload.health_interval_days)).isoformat(),
        validity_days=payload.validity_days,
        baseline_expires_at=(now + timedelta(days=payload.validity_days)).isoformat(),
    )
    monitoring = next((item for item in _monitoring_store.values() if item.get('monitoring_id') == continuity.get('monitoring_id')), None)
    if monitoring is not None:
        monitoring.update(next_successor_hash=payload.successor_next_hash, monitoring_state='certified-next-successor-monitoring-active')
    return {'state': 'telegram-successor-next-baseline-established', 'succession': succession, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'successor-next-baseline-stabilization-and-certification'}


@router.get('/status')
def status() -> dict:
    return {
        'recertification_admissions': len(_admission_store),
        'continuity_restorations': len(_restoration_store),
        'successor_next_baselines': len(_succession_store),
        'external_calls_made': 0,
        'mode': 'expired-renewed-next-successor-recertification-admission-continuity-restoration-succession-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_renewed_next_successor_continuity_v21_362 import command_center as previous
    return previous().replace('v21.362', 'v21.363').replace(
        'AURON TELEGRAM RENEWED NEXT SUCCESSOR CONTINUITY COMMAND CENTER',
        'AURON TELEGRAM EXPIRED RENEWED NEXT SUCCESSOR RESTORATION COMMAND CENTER',
    )
