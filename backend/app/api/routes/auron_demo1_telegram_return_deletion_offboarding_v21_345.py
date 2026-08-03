from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_disclosure_retention_assurance_v21_344 import (
    _attestation_store,
    _exception_store,
    _retention_store,
)

router = APIRouter(prefix='/auron/demo1/v21.345', tags=['auron-demo1-telegram-return-deletion-offboarding'])

_proof_store: dict[str, dict] = {}
_offboarding_store: dict[str, dict] = {}
_residual_exception_store: dict[str, dict] = {}
_COMMIT_PROOF_PHRASE = 'COMMIT AURON TELEGRAM DISCLOSURE RETURN OR DELETION PROOF'
_OFFBOARD_PHRASE = 'OFFBOARD AURON TELEGRAM DISCLOSURE RECIPIENT'
_EXCEPTION_PHRASE = 'OPEN AURON TELEGRAM RESIDUAL COPY EXCEPTION'
_RESOLVE_PHRASE = 'RESOLVE AURON TELEGRAM RESIDUAL COPY EXCEPTION'


class ReturnDeletionProofRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    proof_phrase: str = Field(min_length=1, max_length=320)
    proof_type: str = Field(pattern='^(returned|deleted)$')
    recipient_reference: str = Field(min_length=1, max_length=300)
    proof_statement: str = Field(min_length=1, max_length=1800)


class RecipientOffboardingRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    offboarding_phrase: str = Field(min_length=1, max_length=320)
    access_termination_statement: str = Field(min_length=1, max_length=1800)


class ResidualCopyExceptionOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    exception_phrase: str = Field(min_length=1, max_length=320)
    copy_location: str = Field(min_length=1, max_length=500)
    legal_or_technical_basis: str = Field(min_length=1, max_length=1800)
    remediation_deadline: datetime


class ResidualCopyExceptionResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    resolution_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_return_deletion_offboarding_store() -> None:
    _proof_store.clear()
    _offboarding_store.clear()
    _residual_exception_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _retention_by_id(retention_id: str) -> dict | None:
    return next((item for item in _retention_store.values() if item.get('retention_id') == retention_id), None)


@router.post('/proof/commit')
def commit_return_deletion_proof(payload: ReturnDeletionProofRequest) -> dict:
    if payload.proof_phrase != _COMMIT_PROOF_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit return-or-deletion proof approval required')
    existing = _proof_store.get(payload.retention_id)
    if existing is not None:
        return {'state': 'telegram-return-deletion-proof-already-committed', 'proof': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    retention = _retention_by_id(payload.retention_id)
    if retention is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure retention record not found')
    exception = _exception_store.get(payload.retention_id)
    downstream = _attestation_store.get(payload.retention_id)
    checks = {
        'retention_expired_or_due': retention.get('retention_state') == 'recipient-retention-expired-return-or-deletion-due',
        'no_open_downstream_exception': not bool(exception and exception.get('exception_state') == 'open-downstream-handling-exception'),
        'downstream_attestation_present': bool(downstream and downstream.get('attestation_state') == 'downstream-data-handling-attested'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Return-or-deletion proof blocked', 'blockers': blockers})
    data = {
        'retention_id': retention['retention_id'],
        'delivery_id': retention['delivery_id'],
        'proof_type': payload.proof_type,
        'recipient_reference': payload.recipient_reference,
        'proof_statement': payload.proof_statement,
        'checks': checks,
    }
    proof = {
        'proof_id': str(uuid4()),
        **data,
        'proof_state': f'recipient-{payload.proof_type}-proof-committed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'committed_by': payload.actor,
        'committed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _proof_store[payload.retention_id] = proof
    retention.update(retention_state='return-or-deletion-proof-committed', return_deletion_proof_id=proof['proof_id'])
    return {'state': 'telegram-disclosure-return-deletion-proof-committed', 'proof': proof, 'retention': retention, 'external_calls_made': 0}


@router.post('/offboard')
def offboard_recipient(payload: RecipientOffboardingRequest) -> dict:
    if payload.offboarding_phrase != _OFFBOARD_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit recipient offboarding approval required')
    existing = _offboarding_store.get(payload.retention_id)
    if existing is not None:
        return {'state': 'telegram-recipient-already-offboarded', 'offboarding': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    retention = _retention_by_id(payload.retention_id)
    proof = _proof_store.get(payload.retention_id)
    residual = _residual_exception_store.get(payload.retention_id)
    if retention is None or proof is None:
        raise HTTPException(status_code=409, detail='Committed return-or-deletion proof required before offboarding')
    checks = {
        'proof_immutable': proof.get('immutable') is True and bool(proof.get('integrity_hash')),
        'proof_matches_retention': proof.get('retention_id') == retention.get('retention_id'),
        'no_open_residual_copy_exception': not bool(residual and residual.get('exception_state') == 'open-residual-copy-exception'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Recipient offboarding blocked', 'blockers': blockers})
    data = {
        'retention_id': retention['retention_id'],
        'delivery_id': retention['delivery_id'],
        'proof_id': proof['proof_id'],
        'access_termination_statement': payload.access_termination_statement,
        'checks': checks,
    }
    offboarding = {
        'offboarding_id': str(uuid4()),
        **data,
        'offboarding_state': 'recipient-offboarded-compliance-closed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'offboarded_by': payload.actor,
        'offboarded_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _offboarding_store[payload.retention_id] = offboarding
    retention.update(retention_state='recipient-offboarded-compliance-closed', offboarding_id=offboarding['offboarding_id'])
    return {'state': 'telegram-disclosure-recipient-offboarded', 'offboarding': offboarding, 'retention': retention, 'external_calls_made': 0, 'next_layer': 'post-offboarding-evidence-archive-governance'}


@router.post('/residual-copy/exception/open')
def open_residual_copy_exception(payload: ResidualCopyExceptionOpenRequest) -> dict:
    if payload.exception_phrase != _EXCEPTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit residual-copy exception approval required')
    retention = _retention_by_id(payload.retention_id)
    if retention is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure retention record not found')
    existing = _residual_exception_store.get(payload.retention_id)
    if existing and existing.get('exception_state') == 'open-residual-copy-exception':
        return {'state': 'telegram-residual-copy-exception-already-open', 'exception': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    data = {
        'retention_id': retention['retention_id'],
        'copy_location': payload.copy_location,
        'legal_or_technical_basis': payload.legal_or_technical_basis,
        'remediation_deadline': payload.remediation_deadline.isoformat(),
    }
    exception = {
        'exception_id': str(uuid4()),
        **data,
        'exception_state': 'open-residual-copy-exception',
        'integrity_hash': _hash(data),
        'immutable': True,
        'opened_by': payload.actor,
        'opened_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _residual_exception_store[payload.retention_id] = exception
    retention['retention_state'] = 'residual-copy-exception-active'
    return {'state': 'telegram-residual-copy-exception-opened', 'exception': exception, 'external_calls_made': 0}


@router.post('/residual-copy/exception/resolve')
def resolve_residual_copy_exception(payload: ResidualCopyExceptionResolveRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit residual-copy exception resolution required')
    retention = _retention_by_id(payload.retention_id)
    exception = _residual_exception_store.get(payload.retention_id)
    if retention is None or exception is None:
        raise HTTPException(status_code=404, detail='Telegram residual-copy exception not found')
    if exception.get('exception_state') == 'resolved-residual-copy-exception':
        return {'state': 'telegram-residual-copy-exception-already-resolved', 'exception': exception, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc).isoformat()
    exception.update(exception_state='resolved-residual-copy-exception', resolution_statement=payload.resolution_statement, resolved_by=payload.actor, resolved_at=now)
    retention['retention_state'] = 'recipient-retention-expired-return-or-deletion-due'
    return {'state': 'telegram-residual-copy-exception-resolved', 'exception': exception, 'retention': retention, 'external_calls_made': 0}


@router.get('/status')
def return_deletion_offboarding_status() -> dict:
    return {
        'proofs_committed': len(_proof_store),
        'recipients_offboarded': len(_offboarding_store),
        'residual_exceptions_open': sum(1 for item in _residual_exception_store.values() if item.get('exception_state') == 'open-residual-copy-exception'),
        'external_calls_made': 0,
        'mode': 'return-deletion-proof-recipient-offboarding-residual-copy-exception-governance',
    }


@router.get('/proofs')
def list_proofs() -> dict:
    return {'count': len(_proof_store), 'items': list(_proof_store.values()), 'external_calls_made': 0}


@router.get('/offboardings')
def list_offboardings() -> dict:
    return {'count': len(_offboarding_store), 'items': list(_offboarding_store.values()), 'external_calls_made': 0}


@router.get('/residual-copy/exceptions')
def list_residual_exceptions() -> dict:
    return {'count': len(_residual_exception_store), 'items': list(_residual_exception_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_disclosure_retention_assurance_v21_344 import command_center as v21_344_command_center
    return v21_344_command_center().replace('v21.344', 'v21.345').replace(
        'AURON TELEGRAM DISCLOSURE RETENTION ASSURANCE COMMAND CENTER',
        'AURON TELEGRAM RETURN DELETION OFFBOARDING COMMAND CENTER',
    )
