from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_eight_continuity_v21_407 import (
    _continuity_store,
    _expiry_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.408',
    tags=['auron-demo1-telegram-expired-renewed-successor-next-generation-eight-restoration'],
)

_admission_store: dict[str, dict] = {}
_restoration_store: dict[str, dict] = {}
_succession_store: dict[str, dict] = {}

_ADMIT_PHRASE = 'ADMIT AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION EIGHT RECERTIFICATION'
_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION EIGHT CONTINUITY'
_SUCCESSION_PHRASE = 'ESTABLISH AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE BASELINE'


class RecertificationAdmissionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    admission_phrase: str = Field(min_length=1, max_length=320)
    remediation_reference: str = Field(min_length=1, max_length=300)
    remediation_statement: str = Field(min_length=1, max_length=1800)


class ContinuityRestorationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    admission_id: str = Field(min_length=1, max_length=160)
    restoration_phrase: str = Field(min_length=1, max_length=320)
    observed_expired_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    restoration_reference: str = Field(min_length=1, max_length=300)


class SuccessorBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    restoration_id: str = Field(min_length=1, max_length=160)
    succession_phrase: str = Field(min_length=1, max_length=320)
    successor_next_generation_nine_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    health_check_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)
    succession_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_expired_renewed_successor_next_generation_eight_restoration_store() -> None:
    _admission_store.clear()
    _restoration_store.clear()
    _succession_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _admission_by_id(admission_id: str) -> dict | None:
    return next((item for item in _admission_store.values() if item.get('admission_id') == admission_id), None)


def _restoration_by_id(restoration_id: str) -> dict | None:
    return next((item for item in _restoration_store.values() if item.get('restoration_id') == restoration_id), None)


@router.post('/recertification/admit')
def admit_recertification(payload: RecertificationAdmissionRequest) -> dict:
    if payload.admission_phrase != _ADMIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit expired baseline recertification admission required')
    existing = _admission_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-expired-renewed-successor-next-generation-eight-recertification-already-admitted', 'admission': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    expiry = _expiry_store.get(payload.continuity_id)
    checks = {
        'continuity_expired': continuity is not None and continuity.get('continuity_state') == 'renewed-successor-next-generation-eight-baseline-expired',
        'expiry_immutable': expiry is not None and expiry.get('immutable') is True and bool(expiry.get('integrity_hash')),
        'expiry_links_continuity': expiry is not None and expiry.get('continuity_id') == payload.continuity_id,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Recertification admission blocked', 'blockers': blockers})
    data = {
        'continuity_id': payload.continuity_id,
        'expiry_id': expiry['expiry_id'],
        'expired_hash': expiry['expired_hash'],
        'remediation_reference': payload.remediation_reference,
        'remediation_statement': payload.remediation_statement,
        'checks': checks,
    }
    admission = {
        'admission_id': str(uuid4()),
        **data,
        'admission_state': 'expired-renewed-successor-next-generation-eight-recertification-admitted',
        'integrity_hash': _hash(data),
        'immutable': True,
        'admitted_by': payload.actor,
        'admitted_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _admission_store[payload.continuity_id] = admission
    return {'state': 'telegram-expired-renewed-successor-next-generation-eight-recertification-admitted', 'admission': admission, 'external_calls_made': 0}


@router.post('/continuity/restore')
def restore_continuity(payload: ContinuityRestorationRequest) -> dict:
    if payload.restoration_phrase != _RESTORE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit continuity restoration required')
    admission = _admission_by_id(payload.admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail='Recertification admission required')
    existing = _restoration_store.get(admission['continuity_id'])
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-eight-continuity-already-restored', 'restoration': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    checks = {
        'admission_immutable': admission.get('immutable') is True,
        'expired_hash_matches': payload.observed_expired_hash == admission.get('expired_hash'),
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Continuity restoration blocked', 'blockers': blockers})
    data = {
        'admission_id': admission['admission_id'],
        'continuity_id': admission['continuity_id'],
        'expired_hash': admission['expired_hash'],
        'restoration_reference': payload.restoration_reference,
        'checks': checks,
    }
    restoration = {
        'restoration_id': str(uuid4()),
        **data,
        'restoration_state': 'renewed-successor-next-generation-eight-continuity-restored',
        'integrity_hash': _hash(data),
        'immutable': True,
        'restored_by': payload.actor,
        'restored_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _restoration_store[admission['continuity_id']] = restoration
    return {'state': 'telegram-renewed-successor-next-generation-eight-continuity-restored', 'restoration': restoration, 'external_calls_made': 0}


@router.post('/successor/baseline/establish')
def establish_successor_baseline(payload: SuccessorBaselineRequest) -> dict:
    if payload.succession_phrase != _SUCCESSION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine baseline establishment required')
    restoration = _restoration_by_id(payload.restoration_id)
    if restoration is None:
        raise HTTPException(status_code=404, detail='Completed continuity restoration required')
    existing = _succession_store.get(restoration['continuity_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-baseline-already-active', 'succession': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if payload.successor_next_generation_nine_hash == restoration['expired_hash']:
        raise HTTPException(status_code=409, detail='Successor baseline hash must differ from expired hash')
    now = datetime.now(timezone.utc)
    data = {
        'restoration_id': restoration['restoration_id'],
        'continuity_id': restoration['continuity_id'],
        'superseded_successor_next_generation_eight_hash': restoration['expired_hash'],
        'successor_next_generation_nine_hash': payload.successor_next_generation_nine_hash,
        'health_check_interval_days': payload.health_check_interval_days,
        'next_health_check_due_at': (now + timedelta(days=payload.health_check_interval_days)).isoformat(),
        'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'succession_reference': payload.succession_reference,
    }
    succession = {
        'succession_id': str(uuid4()),
        **data,
        'succession_state': 'successor-next-generation-nine-baseline-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'established_by': payload.actor,
        'established_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _succession_store[restoration['continuity_id']] = succession
    continuity = _continuity_by_id(restoration['continuity_id'])
    if continuity is not None:
        continuity['continuity_state'] = 'renewed-successor-next-generation-eight-baseline-superseded'
        continuity['successor_baseline_id'] = succession['succession_id']
    return {'state': 'telegram-successor-next-generation-nine-baseline-active', 'succession': succession, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'successor-next-generation-nine-stabilization-observation-certification-governance'}


@router.get('/status')
def status() -> dict:
    return {'admissions': len(_admission_store), 'restorations': len(_restoration_store), 'successions': len(_succession_store), 'external_calls_made': 0, 'mode': 'expired-renewed-successor-next-generation-eight-restoration-succession-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.408</title></head><body><h1>AURON TELEGRAM EXPIRED RENEWED SUCCESSOR NEXT GENERATION EIGHT RESTORATION COMMAND CENTER</h1><p>Recertification admission, continuity restoration and successor-next-generation-nine baseline succession governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
