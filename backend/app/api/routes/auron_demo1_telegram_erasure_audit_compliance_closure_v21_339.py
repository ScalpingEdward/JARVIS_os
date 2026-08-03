from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_certificate_retention_erasure_governance_v21_338 import (
    _erasure_store,
    _retention_store,
)
from app.api.routes.auron_demo1_telegram_certificate_retirement_governance_v21_337 import _archive_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _certificate_store

router = APIRouter(prefix='/auron/demo1/v21.339', tags=['auron-demo1-telegram-erasure-audit-compliance-closure'])

_audit_store: dict[str, dict] = {}
_attestation_store: dict[str, dict] = {}
_closure_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM INDEPENDENT ERASURE AUDIT'
_ATTEST_PHRASE = 'ATTEST AURON TELEGRAM ERASURE EVIDENCE CHAIN'
_CLOSE_PHRASE = 'CLOSE AURON TELEGRAM ERASURE COMPLIANCE CASE'


class TelegramErasureAuditStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retirement_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    auditor_independence_statement: str = Field(min_length=1, max_length=1200)


class TelegramErasureAuditAttestRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    audit_id: str = Field(min_length=1, max_length=160)
    attestation_phrase: str = Field(min_length=1, max_length=320)


class TelegramErasureComplianceCloseRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    audit_id: str = Field(min_length=1, max_length=160)
    closure_phrase: str = Field(min_length=1, max_length=320)
    compliance_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_erasure_audit_compliance_closure_store() -> None:
    _audit_store.clear()
    _attestation_store.clear()
    _closure_store.clear()


def _audit_by_id(audit_id: str) -> dict | None:
    return next((item for item in _audit_store.values() if item.get('audit_id') == audit_id), None)


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/start')
def start_independent_erasure_audit(payload: TelegramErasureAuditStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit independent erasure-audit approval required')
    existing = _audit_store.get(payload.retirement_id)
    if existing is not None:
        return {'state': 'telegram-erasure-audit-already-started', 'audit': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    erasure = _erasure_store.get(payload.retirement_id)
    retention = _retention_store.get(payload.retirement_id)
    archive = _archive_store.get(payload.retirement_id)
    if erasure is None or retention is None or archive is None:
        raise HTTPException(status_code=404, detail='Completed erasure evidence chain not found')
    source = _certificate_by_id(erasure['source_certificate_id'])
    successor = _certificate_by_id(erasure['successor_certificate_id'])
    go_live = next((item for item in _go_live_store.values() if item.get('service_certificate_id') == erasure['successor_certificate_id']), None)
    checks = {
        'erasure_committed': erasure.get('erasure_state') == 'cryptographic-erasure-evidence-committed',
        'erasure_hash_present': bool(erasure.get('erasure_evidence_hash')) and erasure.get('immutable') is True,
        'retention_completed': retention.get('retention_state') == 'erasure-completed',
        'archive_is_tombstone': archive.get('archive_state') == 'cryptographically-erased-tombstone',
        'source_is_tombstone': bool(source and source.get('certificate_state') == 'cryptographically-erased-tombstone'),
        'successor_preserved': bool(successor and successor.get('certificate_state') == 'certified'),
        'successor_active': bool(go_live and go_live.get('continuous_mode_active')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Independent erasure audit blocked', 'blockers': blockers})
    chain_payload = {
        'retirement_id': payload.retirement_id,
        'retention_governance_id': retention['retention_governance_id'],
        'archive_id': archive['archive_id'],
        'erasure_id': erasure['erasure_id'],
        'erasure_evidence_hash': erasure['erasure_evidence_hash'],
        'source_certificate_id': erasure['source_certificate_id'],
        'successor_certificate_id': erasure['successor_certificate_id'],
        'checks': checks,
    }
    now = datetime.now(timezone.utc).isoformat()
    audit = {
        'audit_id': str(uuid4()),
        **chain_payload,
        'evidence_chain_hash': _hash(chain_payload),
        'audit_state': 'independent-audit-active-awaiting-attestation',
        'auditor_independence_statement': payload.auditor_independence_statement,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now,
        'external_calls_made': 0,
    }
    _audit_store[payload.retirement_id] = audit
    return {'state': 'telegram-independent-erasure-audit-started', 'audit': audit, 'external_calls_made': 0}


@router.post('/attest')
def attest_erasure_evidence_chain(payload: TelegramErasureAuditAttestRequest) -> dict:
    if payload.attestation_phrase != _ATTEST_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit erasure evidence-chain attestation required')
    audit = _audit_by_id(payload.audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail='Telegram independent erasure audit not found')
    existing = _attestation_store.get(payload.audit_id)
    if existing is not None:
        return {'state': 'telegram-erasure-attestation-already-committed', 'attestation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    erasure = _erasure_store.get(audit['retirement_id'])
    checks = {
        'audit_active': audit.get('audit_state') == 'independent-audit-active-awaiting-attestation',
        'evidence_chain_hash_valid': audit.get('evidence_chain_hash') == _hash({
            'retirement_id': audit['retirement_id'],
            'retention_governance_id': audit['retention_governance_id'],
            'archive_id': audit['archive_id'],
            'erasure_id': audit['erasure_id'],
            'erasure_evidence_hash': audit['erasure_evidence_hash'],
            'source_certificate_id': audit['source_certificate_id'],
            'successor_certificate_id': audit['successor_certificate_id'],
            'checks': audit['checks'],
        }),
        'erasure_record_unchanged': bool(erasure and erasure.get('erasure_evidence_hash') == audit['erasure_evidence_hash']),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Erasure evidence-chain attestation blocked', 'blockers': blockers})
    payload_record = {'audit_id': audit['audit_id'], 'retirement_id': audit['retirement_id'], 'evidence_chain_hash': audit['evidence_chain_hash'], 'checks': checks}
    attestation = {
        'attestation_id': str(uuid4()),
        **payload_record,
        'attestation_state': 'independently-attested-valid-erasure-chain',
        'integrity_hash': _hash(payload_record),
        'immutable': True,
        'attested_by': payload.actor,
        'attested_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    audit['audit_state'] = 'attested-awaiting-compliance-closure'
    audit['attestation_id'] = attestation['attestation_id']
    _attestation_store[payload.audit_id] = attestation
    return {'state': 'telegram-erasure-evidence-chain-attested', 'attestation': attestation, 'external_calls_made': 0}


@router.post('/close')
def close_erasure_compliance_case(payload: TelegramErasureComplianceCloseRequest) -> dict:
    if payload.closure_phrase != _CLOSE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit erasure compliance closure approval required')
    audit = _audit_by_id(payload.audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail='Telegram independent erasure audit not found')
    existing = _closure_store.get(payload.audit_id)
    if existing is not None:
        return {'state': 'telegram-erasure-compliance-already-closed', 'closure': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    attestation = _attestation_store.get(payload.audit_id)
    checks = {
        'audit_attested': audit.get('audit_state') == 'attested-awaiting-compliance-closure',
        'attestation_valid': bool(attestation and attestation.get('attestation_state') == 'independently-attested-valid-erasure-chain'),
        'attestation_immutable': bool(attestation and attestation.get('immutable') is True and attestation.get('integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Erasure compliance closure blocked', 'blockers': blockers})
    closure_payload = {
        'audit_id': audit['audit_id'],
        'attestation_id': attestation['attestation_id'],
        'retirement_id': audit['retirement_id'],
        'compliance_reference': payload.compliance_reference,
        'checks': checks,
    }
    now = datetime.now(timezone.utc).isoformat()
    closure = {
        'closure_id': str(uuid4()),
        **closure_payload,
        'closure_state': 'erasure-compliance-case-closed',
        'integrity_hash': _hash(closure_payload),
        'immutable': True,
        'closed_by': payload.actor,
        'closed_at': now,
        'external_calls_made': 0,
    }
    audit.update(audit_state='completed-compliance-closure', closure_id=closure['closure_id'], completed_at=now)
    _closure_store[payload.audit_id] = closure
    return {'state': 'telegram-erasure-compliance-case-closed', 'closure': closure, 'external_calls_made': 0, 'next_layer': 'long-term-compliance-evidence-monitoring'}


@router.get('/status')
def erasure_audit_status() -> dict:
    audits = list(_audit_store.values())
    return {
        'audits': len(audits),
        'awaiting_attestation': sum(1 for item in audits if item.get('audit_state') == 'independent-audit-active-awaiting-attestation'),
        'awaiting_closure': sum(1 for item in audits if item.get('audit_state') == 'attested-awaiting-compliance-closure'),
        'closed_cases': len(_closure_store),
        'external_calls_made': 0,
        'mode': 'independent-erasure-audit-evidence-chain-attestation-compliance-closure',
    }


@router.get('/audits')
def list_erasure_audits() -> dict:
    return {'count': len(_audit_store), 'items': list(_audit_store.values()), 'external_calls_made': 0}


@router.get('/attestations')
def list_erasure_attestations() -> dict:
    return {'count': len(_attestation_store), 'items': list(_attestation_store.values()), 'external_calls_made': 0}


@router.get('/closures')
def list_compliance_closures() -> dict:
    return {'count': len(_closure_store), 'items': list(_closure_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_certificate_retention_erasure_governance_v21_338 import command_center as v21_338_command_center
    return v21_338_command_center().replace('v21.338', 'v21.339').replace(
        'AURON TELEGRAM CERTIFICATE RETENTION ERASURE GOVERNANCE COMMAND CENTER',
        'AURON TELEGRAM ERASURE AUDIT COMPLIANCE CLOSURE COMMAND CENTER',
    )
