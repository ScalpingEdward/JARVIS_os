from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_post_renewal_continuity_governance_v21_336 import _continuity_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _certificate_store

router = APIRouter(prefix='/auron/demo1/v21.337', tags=['auron-demo1-telegram-certificate-retirement-governance'])

_retirement_store: dict[str, dict] = {}
_archive_store: dict[str, dict] = {}
_AUTHORIZE_PHRASE = 'AUTHORIZE AURON TELEGRAM CERTIFICATE RETIREMENT'
_COMMIT_PHRASE = 'COMMIT AURON TELEGRAM CERTIFICATE RETIREMENT'


class TelegramCertificateRetirementAuthorizeRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    authorization_phrase: str = Field(min_length=1, max_length=300)
    retention_days: int = Field(default=365, ge=30, le=3650)
    reason: str = Field(min_length=1, max_length=1200)


class TelegramCertificateRetirementCommitRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    commit_phrase: str = Field(min_length=1, max_length=300)


def reset_telegram_certificate_retirement_governance_store() -> None:
    _retirement_store.clear()
    _archive_store.clear()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _retirement_by_id(retirement_id: str) -> dict | None:
    return next((item for item in _retirement_store.values() if item.get('retirement_id') == retirement_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/authorize')
def authorize_certificate_retirement(payload: TelegramCertificateRetirementAuthorizeRequest) -> dict:
    if payload.authorization_phrase != _AUTHORIZE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate retirement authorization required')
    existing = _retirement_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-certificate-retirement-already-authorized', 'retirement': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    if continuity is None:
        raise HTTPException(status_code=404, detail='Telegram post-renewal continuity record not found')
    if continuity.get('continuity_state') != 'completed-stable-successor':
        raise HTTPException(status_code=409, detail='Stable successor continuity completion required before retirement')
    source = _certificate_by_id(continuity['source_certificate_id'])
    successor = _certificate_by_id(continuity['successor_certificate_id'])
    if source is None or successor is None:
        raise HTTPException(status_code=409, detail='Source or successor certificate missing')
    go_live = _go_live_store.get(continuity['telegram_chat_id'])
    checks = {
        'source_superseded': source.get('certificate_state') == 'superseded-after-governed-renewal',
        'successor_certified': successor.get('certificate_state') == 'certified',
        'successor_active': bool(go_live and go_live.get('service_certificate_id') == successor['certificate_id']),
        'stabilization_evidence_present': bool(continuity.get('stabilization_integrity_hash')) and continuity.get('stabilization_evidence_immutable') is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certificate retirement authorization blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    retirement_payload = {
        'continuity_id': continuity['continuity_id'],
        'source_certificate_id': source['certificate_id'],
        'successor_certificate_id': successor['certificate_id'],
        'telegram_chat_id': continuity['telegram_chat_id'],
        'retention_days': payload.retention_days,
        'reason': payload.reason,
        'checks': checks,
    }
    retirement = {
        'retirement_id': str(uuid4()),
        **retirement_payload,
        'retirement_state': 'authorized-awaiting-commit',
        'integrity_hash': _hash(retirement_payload),
        'immutable': True,
        'authorized_by': payload.actor,
        'authorized_at': now,
        'external_calls_made': 0,
    }
    _retirement_store[payload.continuity_id] = retirement
    return {'state': 'telegram-certificate-retirement-authorized', 'retirement': retirement, 'external_calls_made': 0}


@router.post('/commit')
def commit_certificate_retirement(payload: TelegramCertificateRetirementCommitRequest) -> dict:
    if payload.commit_phrase != _COMMIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate retirement commit required')
    retirement = _retirement_by_id(payload.retirement_id)
    if retirement is None:
        raise HTTPException(status_code=404, detail='Telegram certificate retirement authorization not found')
    existing = _archive_store.get(payload.retirement_id)
    if existing is not None:
        return {'state': 'telegram-certificate-retirement-already-committed', 'archive': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if retirement.get('retirement_state') != 'authorized-awaiting-commit':
        raise HTTPException(status_code=409, detail='Certificate retirement is not awaiting commit')
    source = _certificate_by_id(retirement['source_certificate_id'])
    successor = _certificate_by_id(retirement['successor_certificate_id'])
    go_live = _go_live_store.get(retirement['telegram_chat_id'])
    checks = {
        'source_still_superseded': bool(source and source.get('certificate_state') == 'superseded-after-governed-renewal'),
        'successor_still_certified': bool(successor and successor.get('certificate_state') == 'certified'),
        'successor_still_active': bool(go_live and successor and go_live.get('service_certificate_id') == successor['certificate_id']),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certificate retirement commit blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    archive_payload = {
        'retirement_id': retirement['retirement_id'],
        'source_certificate_id': source['certificate_id'],
        'successor_certificate_id': successor['certificate_id'],
        'retention_days': retirement['retention_days'],
        'source_integrity_hash': source.get('integrity_hash'),
        'checks': checks,
    }
    archive = {
        'archive_id': str(uuid4()),
        **archive_payload,
        'archive_state': 'retired-certificate-archived-read-only',
        'integrity_hash': _hash(archive_payload),
        'immutable': True,
        'committed_by': payload.actor,
        'committed_at': now,
        'external_calls_made': 0,
    }
    source.update(certificate_state='retired-archived-read-only', retired_at=now, retirement_id=retirement['retirement_id'])
    retirement.update(retirement_state='committed-retired-archived', committed_by=payload.actor, committed_at=now, archive_id=archive['archive_id'])
    _archive_store[payload.retirement_id] = archive
    return {'state': 'telegram-certificate-retirement-committed', 'retirement': retirement, 'archive': archive, 'active_certificate': successor, 'external_calls_made': 0, 'next_layer': 'certificate-retention-expiry-governance'}


@router.get('/status')
def certificate_retirement_status() -> dict:
    items = list(_retirement_store.values())
    return {
        'retirements': len(items),
        'awaiting_commit': sum(1 for item in items if item.get('retirement_state') == 'authorized-awaiting-commit'),
        'committed': sum(1 for item in items if item.get('retirement_state') == 'committed-retired-archived'),
        'archives': len(_archive_store),
        'external_calls_made': 0,
        'mode': 'governed-source-certificate-retirement-read-only-archive',
    }


@router.get('/retirements')
def list_retirements() -> dict:
    return {'count': len(_retirement_store), 'items': list(_retirement_store.values()), 'external_calls_made': 0}


@router.get('/archives')
def list_archives() -> dict:
    return {'count': len(_archive_store), 'items': list(_archive_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_post_renewal_continuity_governance_v21_336 import command_center as v21_336_command_center
    return v21_336_command_center().replace('v21.336', 'v21.337').replace(
        'AURON TELEGRAM POST RENEWAL CONTINUITY GOVERNANCE COMMAND CENTER',
        'AURON TELEGRAM CERTIFICATE RETIREMENT GOVERNANCE COMMAND CENTER',
    )
