from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_post_delivery_compliance_supervision_v21_343 import (
    _confirmation_store,
    _incident_store,
    _supervision_store,
)
from app.api.routes.auron_demo1_telegram_regulator_disclosure_delivery_v21_342 import (
    _acknowledgement_store,
    _delivery_store,
)

router = APIRouter(prefix='/auron/demo1/v21.344', tags=['auron-demo1-telegram-disclosure-retention-assurance'])

_retention_store: dict[str, dict] = {}
_assurance_store: dict[str, list[dict]] = {}
_attestation_store: dict[str, dict] = {}
_exception_store: dict[str, dict] = {}
_ESTABLISH_PHRASE = 'ESTABLISH AURON TELEGRAM DISCLOSURE RETENTION CONTROL'
_REVALIDATE_PHRASE = 'REVALIDATE AURON TELEGRAM RECIPIENT ASSURANCE'
_ATTEST_PHRASE = 'ATTEST AURON TELEGRAM DOWNSTREAM DATA HANDLING'
_EXCEPTION_PHRASE = 'OPEN AURON TELEGRAM DOWNSTREAM HANDLING EXCEPTION'
_RESOLVE_PHRASE = 'RESOLVE AURON TELEGRAM DOWNSTREAM HANDLING EXCEPTION'


class DisclosureRetentionEstablishRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    supervision_id: str = Field(min_length=1, max_length=160)
    establishment_phrase: str = Field(min_length=1, max_length=320)
    recipient_retention_days: int = Field(default=365, ge=1, le=3650)
    assurance_interval_days: int = Field(default=90, ge=1, le=3650)


class DisclosureRetentionEvaluateRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    evaluated_at: datetime | None = None


class RecipientAssuranceRevalidateRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    revalidation_phrase: str = Field(min_length=1, max_length=320)
    assurance_reference: str = Field(min_length=1, max_length=300)
    control_statement: str = Field(min_length=1, max_length=1800)


class DownstreamHandlingAttestRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    attestation_phrase: str = Field(min_length=1, max_length=320)
    processor_name: str = Field(min_length=1, max_length=300)
    purpose_limitation_statement: str = Field(min_length=1, max_length=1800)
    deletion_or_return_commitment: str = Field(min_length=1, max_length=1800)


class DownstreamExceptionOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    exception_phrase: str = Field(min_length=1, max_length=320)
    severity: str = Field(pattern='^(low|medium|high|critical)$')
    reason: str = Field(min_length=1, max_length=1800)


class DownstreamExceptionResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    resolution: str = Field(min_length=1, max_length=1800)


def reset_telegram_disclosure_retention_assurance_store() -> None:
    _retention_store.clear()
    _assurance_store.clear()
    _attestation_store.clear()
    _exception_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _supervision_by_id(supervision_id: str) -> dict | None:
    return next((item for item in _supervision_store.values() if item.get('supervision_id') == supervision_id), None)


def _retention_by_id(retention_id: str) -> dict | None:
    return next((item for item in _retention_store.values() if item.get('retention_id') == retention_id), None)


def _delivery_by_id(delivery_id: str) -> dict | None:
    return next((item for item in _delivery_store.values() if item.get('delivery_id') == delivery_id), None)


def _ack_for_delivery(delivery_id: str) -> dict | None:
    return next((item for item in _acknowledgement_store.values() if item.get('delivery_id') == delivery_id), None)


@router.post('/retention/establish')
def establish_disclosure_retention(payload: DisclosureRetentionEstablishRequest) -> dict:
    if payload.establishment_phrase != _ESTABLISH_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit disclosure retention-control approval required')
    existing = _retention_store.get(payload.supervision_id)
    if existing is not None:
        return {'state': 'telegram-disclosure-retention-already-established', 'retention': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    supervision = _supervision_by_id(payload.supervision_id)
    if supervision is None:
        raise HTTPException(status_code=404, detail='Telegram post-delivery supervision record not found')
    delivery = _delivery_by_id(supervision['delivery_id'])
    acknowledgement = _ack_for_delivery(supervision['delivery_id'])
    incident = _incident_store.get(payload.supervision_id)
    checks = {
        'delivery_accepted': bool(delivery and delivery.get('accepted') is True),
        'delivery_evidence_unchanged': bool(delivery and delivery.get('delivery_evidence_hash') == supervision.get('delivery_evidence_hash')),
        'no_open_incident': not bool(incident and incident.get('incident_state') == 'open-disclosure-incident'),
        'recipient_acknowledgement_present': bool(acknowledgement and acknowledgement.get('acknowledgement_state') == 'recipient-acknowledgement-recorded'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Disclosure retention control blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'supervision_id': supervision['supervision_id'],
        'delivery_id': supervision['delivery_id'],
        'disclosure_id': supervision['disclosure_id'],
        'recipient_retention_days': payload.recipient_retention_days,
        'retention_expires_at': (now + timedelta(days=payload.recipient_retention_days)).isoformat(),
        'assurance_interval_days': payload.assurance_interval_days,
        'next_assurance_due_at': (now + timedelta(days=payload.assurance_interval_days)).isoformat(),
        'delivery_evidence_hash': supervision['delivery_evidence_hash'],
        'checks': checks,
    }
    record = {
        'retention_id': str(uuid4()),
        **data,
        'retention_state': 'active-recipient-retention-control',
        'baseline_hash': _hash(data),
        'assurance_count': 0,
        'immutable': True,
        'established_by': payload.actor,
        'established_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _retention_store[payload.supervision_id] = record
    return {'state': 'telegram-disclosure-retention-control-established', 'retention': record, 'external_calls_made': 0}


@router.post('/retention/evaluate')
def evaluate_disclosure_retention(payload: DisclosureRetentionEvaluateRequest) -> dict:
    record = _retention_by_id(payload.retention_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure retention record not found')
    delivery = _delivery_by_id(record['delivery_id'])
    evaluated_at = payload.evaluated_at or datetime.now(timezone.utc)
    retention_expired = evaluated_at >= datetime.fromisoformat(record['retention_expires_at'])
    assurance_due = evaluated_at >= datetime.fromisoformat(record['next_assurance_due_at'])
    exception = _exception_store.get(record['retention_id'])
    exception_open = bool(exception and exception.get('exception_state') == 'open-downstream-handling-exception')
    checks = {
        'delivery_evidence_unchanged': bool(delivery and delivery.get('delivery_evidence_hash') == record['delivery_evidence_hash']),
        'no_open_exception': not exception_open,
        'downstream_attestation_present': record['retention_id'] in _attestation_store,
    }
    if not checks['delivery_evidence_unchanged']:
        state = 'retention-evidence-drift-exception-required'
    elif exception_open:
        state = 'downstream-handling-exception-active'
    elif retention_expired:
        state = 'recipient-retention-expired-return-or-deletion-due'
    elif assurance_due:
        state = 'recipient-assurance-revalidation-due'
    elif checks['downstream_attestation_present']:
        state = 'active-retention-with-downstream-attestation'
    else:
        state = 'active-recipient-retention-control'
    record.update(retention_state=state, last_evaluated_at=evaluated_at.isoformat(), latest_checks=checks)
    return {'state': f'telegram-{state}', 'retention': record, 'retention_expired': retention_expired, 'assurance_due': assurance_due, 'checks': checks, 'external_calls_made': 0}


@router.post('/assurance/revalidate')
def revalidate_recipient_assurance(payload: RecipientAssuranceRevalidateRequest) -> dict:
    if payload.revalidation_phrase != _REVALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit recipient assurance revalidation required')
    record = _retention_by_id(payload.retention_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure retention record not found')
    exception = _exception_store.get(record['retention_id'])
    if exception and exception.get('exception_state') == 'open-downstream-handling-exception':
        raise HTTPException(status_code=409, detail='Open downstream handling exception blocks assurance revalidation')
    now = datetime.now(timezone.utc)
    sequence = record['assurance_count'] + 1
    data = {
        'retention_id': record['retention_id'],
        'delivery_id': record['delivery_id'],
        'sequence': sequence,
        'assurance_reference': payload.assurance_reference,
        'control_statement': payload.control_statement,
        'baseline_hash': record['baseline_hash'],
    }
    assurance = {
        'assurance_id': str(uuid4()),
        **data,
        'assurance_state': 'recipient-assurance-revalidated',
        'integrity_hash': _hash(data),
        'immutable': True,
        'revalidated_by': payload.actor,
        'revalidated_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _assurance_store.setdefault(record['retention_id'], []).append(assurance)
    record.update(assurance_count=sequence, retention_state='active-recipient-retention-control', next_assurance_due_at=(now + timedelta(days=record['assurance_interval_days'])).isoformat(), last_assurance_id=assurance['assurance_id'])
    return {'state': 'telegram-recipient-assurance-revalidated', 'assurance': assurance, 'retention': record, 'external_calls_made': 0}


@router.post('/downstream/attest')
def attest_downstream_handling(payload: DownstreamHandlingAttestRequest) -> dict:
    if payload.attestation_phrase != _ATTEST_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit downstream data-handling attestation required')
    record = _retention_by_id(payload.retention_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure retention record not found')
    existing = _attestation_store.get(record['retention_id'])
    if existing is not None:
        return {'state': 'telegram-downstream-handling-already-attested', 'attestation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if record['assurance_count'] < 1:
        raise HTTPException(status_code=409, detail='Recipient assurance revalidation required before downstream attestation')
    data = {
        'retention_id': record['retention_id'],
        'delivery_id': record['delivery_id'],
        'processor_name': payload.processor_name,
        'purpose_limitation_statement': payload.purpose_limitation_statement,
        'deletion_or_return_commitment': payload.deletion_or_return_commitment,
        'latest_assurance_id': record['last_assurance_id'],
    }
    attestation = {
        'attestation_id': str(uuid4()),
        **data,
        'attestation_state': 'downstream-data-handling-attested',
        'integrity_hash': _hash(data),
        'immutable': True,
        'attested_by': payload.actor,
        'attested_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _attestation_store[record['retention_id']] = attestation
    record.update(retention_state='active-retention-with-downstream-attestation', downstream_attestation_id=attestation['attestation_id'])
    return {'state': 'telegram-downstream-data-handling-attested', 'attestation': attestation, 'retention': record, 'external_calls_made': 0}


@router.post('/exception/open')
def open_downstream_exception(payload: DownstreamExceptionOpenRequest) -> dict:
    if payload.exception_phrase != _EXCEPTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit downstream handling exception approval required')
    record = _retention_by_id(payload.retention_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure retention record not found')
    existing = _exception_store.get(record['retention_id'])
    if existing and existing.get('exception_state') == 'open-downstream-handling-exception':
        return {'state': 'telegram-downstream-handling-exception-already-open', 'exception': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    data = {'retention_id': record['retention_id'], 'delivery_id': record['delivery_id'], 'severity': payload.severity, 'reason': payload.reason}
    exception = {'exception_id': str(uuid4()), **data, 'exception_state': 'open-downstream-handling-exception', 'integrity_hash': _hash(data), 'immutable': True, 'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _exception_store[record['retention_id']] = exception
    record['retention_state'] = 'downstream-handling-exception-active'
    return {'state': 'telegram-downstream-handling-exception-opened', 'exception': exception, 'external_calls_made': 0}


@router.post('/exception/resolve')
def resolve_downstream_exception(payload: DownstreamExceptionResolveRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit downstream handling exception resolution required')
    record = _retention_by_id(payload.retention_id)
    exception = _exception_store.get(payload.retention_id)
    if record is None or exception is None:
        raise HTTPException(status_code=404, detail='Telegram downstream handling exception not found')
    if exception.get('exception_state') == 'resolved-downstream-handling-exception':
        return {'state': 'telegram-downstream-handling-exception-already-resolved', 'exception': exception, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc).isoformat()
    exception.update(exception_state='resolved-downstream-handling-exception', resolution=payload.resolution, resolved_by=payload.actor, resolved_at=now)
    record['retention_state'] = 'recipient-assurance-revalidation-due'
    return {'state': 'telegram-downstream-handling-exception-resolved', 'exception': exception, 'retention': record, 'external_calls_made': 0, 'next_layer': 'disclosure-return-deletion-proof-and-recipient-offboarding-governance'}


@router.get('/status')
def disclosure_retention_assurance_status() -> dict:
    records = list(_retention_store.values())
    return {
        'retention_records': len(records),
        'assurance_revalidations': sum(len(items) for items in _assurance_store.values()),
        'downstream_attestations': len(_attestation_store),
        'exceptions_open': sum(1 for item in _exception_store.values() if item.get('exception_state') == 'open-downstream-handling-exception'),
        'retention_expired': sum(1 for item in records if item.get('retention_state') == 'recipient-retention-expired-return-or-deletion-due'),
        'external_calls_made': 0,
        'mode': 'disclosure-retention-recipient-assurance-downstream-handling-attestation-governance',
    }


@router.get('/retentions')
def list_retentions() -> dict:
    return {'count': len(_retention_store), 'items': list(_retention_store.values()), 'external_calls_made': 0}


@router.get('/assurances')
def list_assurances() -> dict:
    items = [item for group in _assurance_store.values() for item in group]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/attestations')
def list_attestations() -> dict:
    return {'count': len(_attestation_store), 'items': list(_attestation_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_post_delivery_compliance_supervision_v21_343 import command_center as v21_343_command_center
    return v21_343_command_center().replace('v21.343', 'v21.344').replace(
        'AURON TELEGRAM POST DELIVERY COMPLIANCE SUPERVISION COMMAND CENTER',
        'AURON TELEGRAM DISCLOSURE RETENTION ASSURANCE COMMAND CENTER',
    )
