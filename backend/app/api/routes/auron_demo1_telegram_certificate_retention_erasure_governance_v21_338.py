from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_certificate_retirement_governance_v21_337 import (
    _archive_store,
    _retirement_store,
)
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _certificate_store

router = APIRouter(prefix='/auron/demo1/v21.338', tags=['auron-demo1-telegram-certificate-retention-erasure-governance'])

_retention_store: dict[str, dict] = {}
_legal_hold_store: dict[str, dict] = {}
_erasure_store: dict[str, dict] = {}
_ESTABLISH_PHRASE = 'ESTABLISH AURON TELEGRAM CERTIFICATE RETENTION GOVERNANCE'
_HOLD_PHRASE = 'PLACE AURON TELEGRAM CERTIFICATE LEGAL HOLD'
_RELEASE_PHRASE = 'RELEASE AURON TELEGRAM CERTIFICATE LEGAL HOLD'
_ERASE_PHRASE = 'COMMIT AURON TELEGRAM CERTIFICATE CRYPTOGRAPHIC ERASURE'


class TelegramCertificateRetentionEstablishRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    establishment_phrase: str = Field(min_length=1, max_length=320)


class TelegramCertificateRetentionEvaluateRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    evaluated_at: datetime | None = None


class TelegramCertificateLegalHoldRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    hold_phrase: str = Field(min_length=1, max_length=320)
    legal_basis: str = Field(min_length=1, max_length=1200)
    reference_id: str = Field(min_length=1, max_length=240)


class TelegramCertificateLegalHoldReleaseRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    release_phrase: str = Field(min_length=1, max_length=320)
    release_reason: str = Field(min_length=1, max_length=1200)


class TelegramCertificateErasureCommitRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    erasure_phrase: str = Field(min_length=1, max_length=320)
    erasure_reason: str = Field(min_length=1, max_length=1200)


def reset_telegram_certificate_retention_erasure_governance_store() -> None:
    _retention_store.clear()
    _legal_hold_store.clear()
    _erasure_store.clear()


def _retirement_by_id(retirement_id: str) -> dict | None:
    return next((item for item in _retirement_store.values() if item.get('retirement_id') == retirement_id), None)


def _archive_by_retirement_id(retirement_id: str) -> dict | None:
    return _archive_store.get(retirement_id)


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@router.post('/establish')
def establish_retention_governance(payload: TelegramCertificateRetentionEstablishRequest) -> dict:
    if payload.establishment_phrase != _ESTABLISH_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate retention governance approval required')
    existing = _retention_store.get(payload.retirement_id)
    if existing is not None:
        return {'state': 'telegram-certificate-retention-governance-already-established', 'retention': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    retirement = _retirement_by_id(payload.retirement_id)
    archive = _archive_by_retirement_id(payload.retirement_id)
    if retirement is None or archive is None:
        raise HTTPException(status_code=404, detail='Committed certificate retirement archive not found')
    if retirement.get('retirement_state') != 'committed-retired-archived' or archive.get('archive_state') != 'retired-certificate-archived-read-only':
        raise HTTPException(status_code=409, detail='Committed read-only archive required before retention governance')
    committed_at = _parse(archive.get('committed_at')) or datetime.now(timezone.utc)
    expires_at = committed_at + timedelta(days=int(archive['retention_days']))
    retention_payload = {
        'retirement_id': payload.retirement_id,
        'archive_id': archive['archive_id'],
        'source_certificate_id': archive['source_certificate_id'],
        'successor_certificate_id': archive['successor_certificate_id'],
        'retention_days': archive['retention_days'],
        'retention_started_at': committed_at.isoformat(),
        'retention_expires_at': expires_at.isoformat(),
        'archive_integrity_hash': archive['integrity_hash'],
    }
    record = {
        'retention_governance_id': str(uuid4()),
        **retention_payload,
        'retention_state': 'active-retention-window',
        'legal_hold_active': False,
        'integrity_hash': _hash(retention_payload),
        'immutable': True,
        'established_by': payload.actor,
        'established_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _retention_store[payload.retirement_id] = record
    return {'state': 'telegram-certificate-retention-governance-established', 'retention': record, 'external_calls_made': 0}


@router.post('/evaluate')
def evaluate_retention_expiry(payload: TelegramCertificateRetentionEvaluateRequest) -> dict:
    record = _retention_store.get(payload.retirement_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram certificate retention governance not found')
    evaluated_at = payload.evaluated_at or datetime.now(timezone.utc)
    expires_at = _parse(record['retention_expires_at'])
    expired = bool(expires_at and evaluated_at >= expires_at)
    hold = _legal_hold_store.get(payload.retirement_id)
    hold_active = bool(hold and hold.get('hold_state') == 'active-legal-hold')
    state = 'retention-expired-legal-hold' if expired and hold_active else ('retention-expired-erasure-eligible' if expired else 'active-retention-window')
    record.update(retention_state=state, legal_hold_active=hold_active, last_evaluated_at=evaluated_at.isoformat())
    evaluation = {
        'retirement_id': payload.retirement_id,
        'retention_state': state,
        'expired': expired,
        'legal_hold_active': hold_active,
        'erasure_eligible': expired and not hold_active,
        'evaluated_by': payload.actor,
        'evaluated_at': evaluated_at.isoformat(),
        'external_calls_made': 0,
    }
    record['latest_evaluation'] = evaluation
    return {'state': f'telegram-certificate-{state}', 'evaluation': evaluation, 'external_calls_made': 0}


@router.post('/legal-hold')
def place_legal_hold(payload: TelegramCertificateLegalHoldRequest) -> dict:
    if payload.hold_phrase != _HOLD_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate legal-hold approval required')
    if payload.retirement_id not in _retention_store:
        raise HTTPException(status_code=404, detail='Telegram certificate retention governance not found')
    existing = _legal_hold_store.get(payload.retirement_id)
    if existing and existing.get('hold_state') == 'active-legal-hold':
        return {'state': 'telegram-certificate-legal-hold-already-active', 'legal_hold': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    hold_payload = {'retirement_id': payload.retirement_id, 'legal_basis': payload.legal_basis, 'reference_id': payload.reference_id}
    hold = {
        'legal_hold_id': str(uuid4()),
        **hold_payload,
        'hold_state': 'active-legal-hold',
        'integrity_hash': _hash(hold_payload),
        'immutable': True,
        'placed_by': payload.actor,
        'placed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _legal_hold_store[payload.retirement_id] = hold
    _retention_store[payload.retirement_id].update(legal_hold_active=True, retention_state='legal-hold-active')
    return {'state': 'telegram-certificate-legal-hold-placed', 'legal_hold': hold, 'external_calls_made': 0}


@router.post('/legal-hold/release')
def release_legal_hold(payload: TelegramCertificateLegalHoldReleaseRequest) -> dict:
    if payload.release_phrase != _RELEASE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate legal-hold release approval required')
    hold = _legal_hold_store.get(payload.retirement_id)
    if hold is None:
        raise HTTPException(status_code=404, detail='Telegram certificate legal hold not found')
    if hold.get('hold_state') == 'released-legal-hold':
        return {'state': 'telegram-certificate-legal-hold-already-released', 'legal_hold': hold, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc).isoformat()
    hold.update(hold_state='released-legal-hold', released_by=payload.actor, released_at=now, release_reason=payload.release_reason)
    record = _retention_store[payload.retirement_id]
    record['legal_hold_active'] = False
    record['retention_state'] = 'retention-expired-erasure-eligible' if record.get('latest_evaluation', {}).get('expired') else 'active-retention-window'
    return {'state': 'telegram-certificate-legal-hold-released', 'legal_hold': hold, 'external_calls_made': 0}


@router.post('/erase')
def commit_cryptographic_erasure(payload: TelegramCertificateErasureCommitRequest) -> dict:
    if payload.erasure_phrase != _ERASE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit governed cryptographic erasure approval required')
    existing = _erasure_store.get(payload.retirement_id)
    if existing is not None:
        return {'state': 'telegram-certificate-erasure-already-committed', 'erasure': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    record = _retention_store.get(payload.retirement_id)
    archive = _archive_by_retirement_id(payload.retirement_id)
    if record is None or archive is None:
        raise HTTPException(status_code=404, detail='Telegram certificate retention archive not found')
    evaluation = record.get('latest_evaluation')
    checks = {
        'retention_expired': bool(evaluation and evaluation.get('expired')),
        'erasure_eligible': bool(evaluation and evaluation.get('erasure_eligible')),
        'no_active_legal_hold': not record.get('legal_hold_active'),
        'archive_read_only': archive.get('archive_state') == 'retired-certificate-archived-read-only',
    }
    source = _certificate_by_id(record['source_certificate_id'])
    successor = _certificate_by_id(record['successor_certificate_id'])
    go_live = next((item for item in _go_live_store.values() if item.get('service_certificate_id') == record['successor_certificate_id']), None)
    checks.update({
        'source_not_active': not bool(go_live and go_live.get('service_certificate_id') == record['source_certificate_id']),
        'successor_preserved': bool(successor and successor.get('certificate_state') == 'certified'),
    })
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Governed certificate erasure blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    erasure_payload = {
        'retirement_id': payload.retirement_id,
        'archive_id': archive['archive_id'],
        'source_certificate_id': record['source_certificate_id'],
        'successor_certificate_id': record['successor_certificate_id'],
        'archive_integrity_hash_before_erasure': archive['integrity_hash'],
        'erasure_reason': payload.erasure_reason,
        'checks': checks,
    }
    erasure = {
        'erasure_id': str(uuid4()),
        **erasure_payload,
        'erasure_state': 'cryptographic-erasure-evidence-committed',
        'erasure_evidence_hash': _hash(erasure_payload),
        'immutable': True,
        'committed_by': payload.actor,
        'committed_at': now,
        'external_calls_made': 0,
    }
    archive.update(archive_state='cryptographically-erased-tombstone', erased_at=now, erasure_id=erasure['erasure_id'], source_integrity_hash=None)
    if source is not None:
        source.update(certificate_state='cryptographically-erased-tombstone', erased_at=now, integrity_hash=None)
    record.update(retention_state='erasure-completed', erasure_id=erasure['erasure_id'], erased_at=now)
    _erasure_store[payload.retirement_id] = erasure
    return {'state': 'telegram-certificate-cryptographic-erasure-committed', 'erasure': erasure, 'active_certificate': successor, 'external_calls_made': 0, 'next_layer': 'erasure-audit-attestation-governance'}


@router.get('/status')
def retention_erasure_status() -> dict:
    records = list(_retention_store.values())
    return {
        'retention_records': len(records),
        'active_windows': sum(1 for item in records if item.get('retention_state') == 'active-retention-window'),
        'legal_holds_active': sum(1 for item in _legal_hold_store.values() if item.get('hold_state') == 'active-legal-hold'),
        'erasure_eligible': sum(1 for item in records if item.get('retention_state') == 'retention-expired-erasure-eligible'),
        'erasures_committed': len(_erasure_store),
        'external_calls_made': 0,
        'mode': 'retention-expiry-legal-hold-governed-cryptographic-erasure',
    }


@router.get('/retentions')
def list_retentions() -> dict:
    return {'count': len(_retention_store), 'items': list(_retention_store.values()), 'external_calls_made': 0}


@router.get('/legal-holds')
def list_legal_holds() -> dict:
    return {'count': len(_legal_hold_store), 'items': list(_legal_hold_store.values()), 'external_calls_made': 0}


@router.get('/erasures')
def list_erasures() -> dict:
    return {'count': len(_erasure_store), 'items': list(_erasure_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_certificate_retirement_governance_v21_337 import command_center as v21_337_command_center
    return v21_337_command_center().replace('v21.337', 'v21.338').replace(
        'AURON TELEGRAM CERTIFICATE RETIREMENT GOVERNANCE COMMAND CENTER',
        'AURON TELEGRAM CERTIFICATE RETENTION ERASURE GOVERNANCE COMMAND CENTER',
    )
