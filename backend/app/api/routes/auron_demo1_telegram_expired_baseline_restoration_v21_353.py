from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_renewed_assurance_continuity_v21_352 import (
    _continuity_store,
    _expiry_store,
    _health_check_store,
)
from app.api.routes.auron_demo1_telegram_assurance_recertification_v21_351 import _baseline_store
from app.api.routes.auron_demo1_telegram_certified_reclosure_assurance_v21_350 import _assurance_store

router = APIRouter(prefix='/auron/demo1/v21.353', tags=['auron-demo1-telegram-expired-baseline-restoration'])

_admission_store: dict[str, dict] = {}
_restoration_store: dict[str, dict] = {}
_successor_store: dict[str, dict] = {}
_ADMIT_PHRASE = 'ADMIT AURON TELEGRAM EXPIRED BASELINE RECERTIFICATION'
_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM ASSURANCE CONTINUITY'
_SUCCEED_PHRASE = 'ESTABLISH AURON TELEGRAM SUCCESSOR ASSURANCE BASELINE'


class ExpiredBaselineRecertificationAdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    admission_phrase: str = Field(min_length=1, max_length=320)
    admission_reference: str = Field(min_length=1, max_length=300)
    remediation_statement: str = Field(min_length=1, max_length=1800)


class ContinuityRestorationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    restoration_phrase: str = Field(min_length=1, max_length=320)
    observed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    restoration_reference: str = Field(min_length=1, max_length=300)
    restoration_statement: str = Field(min_length=1, max_length=1800)


class SuccessorBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    succession_phrase: str = Field(min_length=1, max_length=320)
    successor_reference: str = Field(min_length=1, max_length=300)
    successor_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    validity_days: int = Field(default=365, ge=1, le=36500)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)


def reset_telegram_expired_baseline_restoration_store() -> None:
    _admission_store.clear()
    _restoration_store.clear()
    _successor_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _baseline_by_id(baseline_id: str) -> dict | None:
    return next((item for item in _baseline_store.values() if item.get('baseline_id') == baseline_id), None)


def _assurance_by_id(assurance_id: str) -> dict | None:
    return next((item for item in _assurance_store.values() if item.get('assurance_id') == assurance_id), None)


@router.post('/recertification/admit')
def admit_expired_baseline_recertification(payload: ExpiredBaselineRecertificationAdmissionRequest) -> dict:
    if payload.admission_phrase != _ADMIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit expired-baseline recertification admission required')
    existing = _admission_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-expired-baseline-recertification-already-admitted', 'admission': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or expiry is None:
        raise HTTPException(status_code=404, detail='Expired renewed-assurance baseline not found')
    baseline = _baseline_by_id(continuity['baseline_id'])
    assurance = _assurance_by_id(continuity['assurance_id'])
    checks = {
        'baseline_expired': expiry.get('expiry_state') == 'renewed-assurance-baseline-expired',
        'expiry_immutable': expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),
        'continuity_expired': continuity.get('continuity_state') == 'renewed-assurance-baseline-expired',
        'baseline_present': baseline is not None and baseline.get('immutable') is True,
        'assurance_present': assurance is not None,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Expired-baseline recertification admission blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'],
        'baseline_id': continuity['baseline_id'],
        'assurance_id': continuity['assurance_id'],
        'expiry_id': expiry['expiry_id'],
        'expired_baseline_hash': continuity['active_baseline_hash'],
        'admission_reference': payload.admission_reference,
        'remediation_statement': payload.remediation_statement,
        'checks': checks,
    }
    admission = {
        'admission_id': str(uuid4()),
        **data,
        'admission_state': 'expired-baseline-recertification-admitted',
        'integrity_hash': _hash(data),
        'immutable': True,
        'admitted_by': payload.actor,
        'admitted_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _admission_store[payload.continuity_id] = admission
    continuity['continuity_state'] = 'expired-baseline-restoration-admitted'
    return {'state': 'telegram-expired-baseline-recertification-admitted', 'admission': admission, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/continuity/restore')
def restore_assurance_continuity(payload: ContinuityRestorationRequest) -> dict:
    if payload.restoration_phrase != _RESTORE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit assurance continuity restoration required')
    existing = _restoration_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-assurance-continuity-already-restored', 'restoration': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    admission = _admission_store.get(payload.continuity_id)
    if continuity is None or admission is None:
        raise HTTPException(status_code=409, detail='Expired-baseline recertification admission required before restoration')
    hash_matches = payload.observed_baseline_hash == continuity.get('active_baseline_hash')
    checks = {
        'admission_complete': admission.get('admission_state') == 'expired-baseline-recertification-admitted',
        'admission_immutable': admission.get('immutable') is True and bool(admission.get('integrity_hash')),
        'expired_hash_verified': hash_matches,
        'control_healthy': payload.control_state == 'healthy',
        'continuity_admitted': continuity.get('continuity_state') == 'expired-baseline-restoration-admitted',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Assurance continuity restoration blocked', 'blockers': blockers})
    data = {
        'continuity_id': continuity['continuity_id'],
        'admission_id': admission['admission_id'],
        'verified_expired_baseline_hash': payload.observed_baseline_hash,
        'control_state': payload.control_state,
        'restoration_reference': payload.restoration_reference,
        'restoration_statement': payload.restoration_statement,
        'checks': checks,
    }
    restoration = {
        'restoration_id': str(uuid4()),
        **data,
        'restoration_state': 'assurance-continuity-restored-awaiting-successor-baseline',
        'integrity_hash': _hash(data),
        'immutable': True,
        'restored_by': payload.actor,
        'restored_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _restoration_store[payload.continuity_id] = restoration
    continuity['continuity_state'] = 'restored-awaiting-successor-baseline'
    return {'state': 'telegram-assurance-continuity-restored', 'restoration': restoration, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/succeed')
def establish_successor_assurance_baseline(payload: SuccessorBaselineRequest) -> dict:
    if payload.succession_phrase != _SUCCEED_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor assurance baseline approval required')
    existing = _successor_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-successor-assurance-baseline-already-established', 'successor': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    restoration = _restoration_store.get(payload.continuity_id)
    admission = _admission_store.get(payload.continuity_id)
    if continuity is None or restoration is None or admission is None:
        raise HTTPException(status_code=409, detail='Completed continuity restoration required before baseline succession')
    checks = {
        'restoration_complete': restoration.get('restoration_state') == 'assurance-continuity-restored-awaiting-successor-baseline',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'admission_immutable': admission.get('immutable') is True and bool(admission.get('integrity_hash')),
        'successor_hash_differs': payload.successor_baseline_hash != continuity.get('active_baseline_hash'),
        'continuity_awaiting_successor': continuity.get('continuity_state') == 'restored-awaiting-successor-baseline',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor assurance baseline blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'continuity_id': continuity['continuity_id'],
        'assurance_id': continuity['assurance_id'],
        'restoration_id': restoration['restoration_id'],
        'superseded_baseline_id': continuity['baseline_id'],
        'superseded_baseline_hash': continuity['active_baseline_hash'],
        'successor_baseline_hash': payload.successor_baseline_hash,
        'successor_reference': payload.successor_reference,
        'validity_days': payload.validity_days,
        'health_check_interval_days': payload.health_check_interval_days,
        'checks': checks,
    }
    successor = {
        'successor_id': str(uuid4()),
        **data,
        'successor_state': 'successor-assurance-baseline-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'established_by': payload.actor,
        'established_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _successor_store[payload.continuity_id] = successor
    expiry = _expiry_store.get(payload.continuity_id)
    if expiry is not None:
        expiry.update(expiry_state='expired-baseline-superseded', successor_id=successor['successor_id'])
    continuity.update(
        continuity_state='renewed-assurance-continuity-active',
        superseded_baseline_id=continuity['baseline_id'],
        superseded_baseline_hash=continuity['active_baseline_hash'],
        active_baseline_hash=payload.successor_baseline_hash,
        successor_id=successor['successor_id'],
        health_check_interval_days=payload.health_check_interval_days,
        health_check_count=0,
        next_health_check_due_at=(now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        baseline_validity_days=payload.validity_days,
        baseline_expires_at=(now + timedelta(days=payload.validity_days)).isoformat(),
    )
    _health_check_store[continuity['continuity_id']] = []
    assurance = _assurance_by_id(continuity['assurance_id'])
    if assurance is not None:
        assurance.update(corrected_evidence_hash=payload.successor_baseline_hash, assurance_state='certified-reclosure-long-term-assurance-active')
    return {'state': 'telegram-successor-assurance-baseline-established', 'successor': successor, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'successor-baseline-stabilization-and-continuity-certification'}


@router.get('/status')
def expired_baseline_restoration_status() -> dict:
    return {
        'recertification_admissions': len(_admission_store),
        'continuity_restorations': len(_restoration_store),
        'successor_baselines': len(_successor_store),
        'awaiting_successor': sum(1 for item in _continuity_store.values() if item.get('continuity_state') == 'restored-awaiting-successor-baseline'),
        'external_calls_made': 0,
        'mode': 'expired-baseline-recertification-admission-continuity-restoration-successor-baseline-governance',
    }


@router.get('/admissions')
def list_admissions() -> dict:
    return {'count': len(_admission_store), 'items': list(_admission_store.values()), 'external_calls_made': 0}


@router.get('/restorations')
def list_restorations() -> dict:
    return {'count': len(_restoration_store), 'items': list(_restoration_store.values()), 'external_calls_made': 0}


@router.get('/successors')
def list_successors() -> dict:
    return {'count': len(_successor_store), 'items': list(_successor_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_renewed_assurance_continuity_v21_352 import command_center as v21_352_command_center
    return v21_352_command_center().replace('v21.352', 'v21.353').replace(
        'AURON TELEGRAM RENEWED ASSURANCE CONTINUITY COMMAND CENTER',
        'AURON TELEGRAM EXPIRED BASELINE RESTORATION COMMAND CENTER',
    )
