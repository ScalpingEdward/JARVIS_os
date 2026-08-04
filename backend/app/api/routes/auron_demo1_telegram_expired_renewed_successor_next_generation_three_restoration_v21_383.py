from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_three_continuity_v21_382 import (
    _continuity_store,
    _expiry_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_three_recertification_v21_381 import _baseline_store
from app.api.routes.auron_demo1_telegram_successor_next_generation_three_monitoring_v21_380 import _monitoring_store

router = APIRouter(
    prefix='/auron/demo1/v21.383',
    tags=['auron-demo1-telegram-expired-renewed-successor-next-generation-three-restoration'],
)

_admission_store: dict[str, dict] = {}
_restoration_store: dict[str, dict] = {}
_succession_store: dict[str, dict] = {}

_ADMIT_PHRASE = 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION THREE RECERTIFICATION'
_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION THREE CONTINUITY'
_ESTABLISH_PHRASE = 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR BASELINE'


class AdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    admission_phrase: str = Field(min_length=1, max_length=320)
    remediation_reference: str = Field(min_length=1, max_length=300)
    remediation_statement: str = Field(min_length=1, max_length=1800)


class RestorationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    restoration_phrase: str = Field(min_length=1, max_length=320)
    observed_expired_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    restoration_reference: str = Field(min_length=1, max_length=300)
    restoration_statement: str = Field(min_length=1, max_length=1800)


class SuccessorBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    establishment_phrase: str = Field(min_length=1, max_length=320)
    successor_next_generation_four_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    baseline_reference: str = Field(min_length=1, max_length=300)
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)


def reset_telegram_expired_renewed_successor_next_generation_three_restoration_store() -> None:
    _admission_store.clear()
    _restoration_store.clear()
    _succession_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _continuity(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


@router.post('/recertification/admit')
def admit(payload: AdmissionRequest) -> dict:
    if payload.admission_phrase != _ADMIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit expired renewed successor-next-generation-three admission required')
    if payload.continuity_id in _admission_store:
        return {'state': 'telegram-expired-renewed-successor-next-generation-three-recertification-already-admitted', 'admission': _admission_store[payload.continuity_id], 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or expiry is None:
        raise HTTPException(status_code=409, detail='Immutable v21.382 expiry evidence required')
    checks = {
        'baseline_expired': continuity.get('continuity_state') == 'renewed-successor-next-generation-three-baseline-expired-recertification-required',
        'expiry_complete': expiry.get('expiry_state') == 'renewed-successor-next-generation-three-baseline-expired',
        'expiry_immutable': expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),
        'hash_consistent': expiry.get('expired_baseline_hash') == continuity.get('active_baseline_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Recertification admission blocked', 'blockers': blockers})
    data = {'continuity_id': payload.continuity_id, 'monitoring_id': continuity['monitoring_id'], 'expiry_id': expiry['expiry_id'], 'expired_baseline_hash': expiry['expired_baseline_hash'], 'remediation_reference': payload.remediation_reference, 'remediation_statement': payload.remediation_statement, 'checks': checks}
    admission = {'admission_id': str(uuid4()), **data, 'admission_state': 'expired-renewed-successor-next-generation-three-recertification-admitted', 'integrity_hash': _hash(data), 'immutable': True, 'admitted_by': payload.actor, 'admitted_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _admission_store[payload.continuity_id] = admission
    return {'state': 'telegram-expired-renewed-successor-next-generation-three-recertification-admitted', 'admission': admission, 'external_calls_made': 0}


@router.post('/continuity/restore')
def restore(payload: RestorationRequest) -> dict:
    if payload.restoration_phrase != _RESTORE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit continuity restoration required')
    if payload.continuity_id in _restoration_store:
        return {'state': 'telegram-renewed-successor-next-generation-three-continuity-already-restored', 'restoration': _restoration_store[payload.continuity_id], 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity(payload.continuity_id)
    admission = _admission_store.get(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    if continuity is None or admission is None or expiry is None:
        raise HTTPException(status_code=409, detail='Completed recertification admission required')
    expected_hash = expiry.get('expired_baseline_hash')
    checks = {
        'admission_complete': admission.get('admission_state') == 'expired-renewed-successor-next-generation-three-recertification-admitted',
        'admission_immutable': admission.get('immutable') is True and bool(admission.get('integrity_hash')),
        'expired_hash_matches': bool(expected_hash) and payload.observed_expired_hash == expected_hash,
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity restoration blocked', 'blockers': blockers})
    data = {'continuity_id': payload.continuity_id, 'monitoring_id': continuity['monitoring_id'], 'admission_id': admission['admission_id'], 'expiry_id': expiry['expiry_id'], 'expired_baseline_hash': expected_hash, 'restoration_reference': payload.restoration_reference, 'restoration_statement': payload.restoration_statement, 'checks': checks}
    restoration = {'restoration_id': str(uuid4()), **data, 'restoration_state': 'renewed-successor-next-generation-three-continuity-restored-awaiting-successor-next-generation-four-baseline', 'integrity_hash': _hash(data), 'immutable': True, 'restored_by': payload.actor, 'restored_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _restoration_store[payload.continuity_id] = restoration
    continuity['continuity_state'] = 'renewed-successor-next-generation-three-continuity-restored'
    return {'state': 'telegram-renewed-successor-next-generation-three-continuity-restored', 'restoration': restoration, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/baseline/establish')
def establish(payload: SuccessorBaselineRequest) -> dict:
    if payload.establishment_phrase != _ESTABLISH_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-four baseline establishment required')
    if payload.continuity_id in _succession_store:
        return {'state': 'telegram-successor-next-generation-four-baseline-already-active', 'succession': _succession_store[payload.continuity_id], 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity(payload.continuity_id)
    restoration = _restoration_store.get(payload.continuity_id)
    admission = _admission_store.get(payload.continuity_id)
    if continuity is None or restoration is None or admission is None:
        raise HTTPException(status_code=409, detail='Completed continuity restoration required')
    previous_hash = restoration['expired_baseline_hash']
    checks = {
        'restoration_complete': restoration.get('restoration_state') == 'renewed-successor-next-generation-three-continuity-restored-awaiting-successor-next-generation-four-baseline',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'successor_hash_distinct': payload.successor_next_generation_four_hash != previous_hash,
        'admission_linked': restoration.get('admission_id') == admission.get('admission_id'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor baseline establishment blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {'continuity_id': payload.continuity_id, 'monitoring_id': continuity['monitoring_id'], 'admission_id': admission['admission_id'], 'restoration_id': restoration['restoration_id'], 'superseded_baseline_hash': previous_hash, 'successor_next_generation_four_hash': payload.successor_next_generation_four_hash, 'baseline_reference': payload.baseline_reference, 'health_check_interval_days': payload.health_check_interval_days, 'validity_days': payload.validity_days, 'checks': checks}
    succession = {'succession_id': str(uuid4()), **data, 'succession_state': 'successor-next-generation-four-baseline-active', 'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(), 'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(), 'integrity_hash': _hash(data), 'immutable': True, 'established_by': payload.actor, 'established_at': now.isoformat(), 'external_calls_made': 0}
    _succession_store[payload.continuity_id] = succession
    continuity.update(continuity_state='successor-next-generation-four-baseline-active', superseded_baseline_hash=previous_hash, active_baseline_hash=payload.successor_next_generation_four_hash, successor_next_generation_four_baseline_id=succession['succession_id'], valid_until=succession['valid_until'], next_health_check_due_at=succession['next_health_check_due_at'])
    monitoring = next((item for item in _monitoring_store.values() if item.get('monitoring_id') == continuity.get('monitoring_id')), None)
    if monitoring is not None:
        monitoring.update(monitoring_state='successor-next-generation-four-baseline-active', active_successor_next_generation_three_hash=payload.successor_next_generation_four_hash, superseded_successor_next_generation_three_hash=previous_hash)
    baseline = _baseline_store.get(continuity['monitoring_id'])
    if baseline is not None:
        baseline.update(baseline_state='renewed-successor-next-generation-three-baseline-superseded', superseded_by_succession_id=succession['succession_id'])
    return {'state': 'telegram-successor-next-generation-four-baseline-established', 'succession': succession, 'continuity': continuity, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'successor-next-generation-four-stabilization-and-certification'}


@router.get('/status')
def status() -> dict:
    return {'recertification_admissions': len(_admission_store), 'continuity_restorations': len(_restoration_store), 'successor_baselines': len(_succession_store), 'external_calls_made': 0, 'mode': 'expired-renewed-successor-next-generation-three-restoration-and-succession'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.383</title></head><body><h1>AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION THREE RESTORATION COMMAND CENTER</h1><p>Recertification admission, continuity restoration and successor-next-generation-four baseline governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
