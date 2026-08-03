from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_post_offboarding_closure_v21_346 import (
    _archive_store,
    _closure_store,
    _risk_review_store,
)

router = APIRouter(prefix='/auron/demo1/v21.347', tags=['auron-demo1-telegram-closed-record-integrity'])

_record_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_revalidation_store: dict[str, list[dict]] = {}
_reopen_store: dict[str, dict] = {}
_RETAIN_PHRASE = 'RETAIN AURON TELEGRAM CLOSED DISCLOSURE RECORD'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM CLOSED DISCLOSURE INTEGRITY'
_REVALIDATE_PHRASE = 'REVALIDATE AURON TELEGRAM DISCLOSURE LIFECYCLE CLOSURE'
_REOPEN_PHRASE = 'REOPEN AURON TELEGRAM DISCLOSURE COMPLIANCE CASE'


class ClosedDisclosureRecordRetainRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    archive_id: str = Field(min_length=1, max_length=160)
    retain_phrase: str = Field(min_length=1, max_length=320)
    retention_days: int = Field(default=2555, ge=1, le=36500)
    audit_interval_days: int = Field(default=180, ge=1, le=3650)


class ClosedDisclosureIntegrityAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    audited_at: datetime | None = None


class ClosureRevalidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    revalidation_phrase: str = Field(min_length=1, max_length=320)
    revalidation_reference: str = Field(min_length=1, max_length=300)


class ComplianceCaseReopenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    reopen_phrase: str = Field(min_length=1, max_length=320)
    reason: str = Field(min_length=1, max_length=1800)
    severity: str = Field(pattern='^(low|medium|high|critical)$')


def reset_telegram_closed_record_integrity_store() -> None:
    _record_store.clear()
    _audit_store.clear()
    _revalidation_store.clear()
    _reopen_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _archive_by_id(archive_id: str) -> dict | None:
    return next((item for item in _archive_store.values() if item.get('archive_id') == archive_id), None)


def _record_by_id(record_id: str) -> dict | None:
    return next((item for item in _record_store.values() if item.get('record_id') == record_id), None)


def _closure_for_archive(archive_id: str) -> dict | None:
    return _closure_store.get(archive_id)


def _review_for_archive(archive_id: str) -> dict | None:
    return _risk_review_store.get(archive_id)


def _evidence_payload(archive: dict, closure: dict, review: dict) -> dict:
    return {
        'archive_id': archive['archive_id'],
        'archive_hash': archive['archive_hash'],
        'archive_reference': archive['archive_reference'],
        'retention_id': archive['retention_id'],
        'closure_id': closure['closure_id'],
        'closure_integrity_hash': closure['integrity_hash'],
        'closure_reference': closure['closure_reference'],
        'risk_review_id': review['risk_review_id'],
        'risk_review_integrity_hash': review['integrity_hash'],
        'risk_rating': review['risk_rating'],
    }


@router.post('/record/retain')
def retain_closed_disclosure_record(payload: ClosedDisclosureRecordRetainRequest) -> dict:
    if payload.retain_phrase != _RETAIN_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit closed-disclosure record retention approval required')
    existing = _record_store.get(payload.archive_id)
    if existing is not None:
        return {'state': 'telegram-closed-disclosure-record-already-retained', 'record': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    archive = _archive_by_id(payload.archive_id)
    closure = _closure_for_archive(payload.archive_id)
    review = _review_for_archive(payload.archive_id)
    if archive is None or closure is None or review is None:
        raise HTTPException(status_code=404, detail='Completed v21.346 closure evidence not found')
    checks = {
        'archive_finally_closed': archive.get('archive_state') == 'archived-final-lifecycle-closed',
        'archive_immutable': archive.get('immutable') is True and bool(archive.get('archive_hash')),
        'closure_final': closure.get('closure_state') == 'final-disclosure-lifecycle-closed',
        'closure_immutable': closure.get('immutable') is True and bool(closure.get('integrity_hash')),
        'risk_review_acceptable': review.get('closure_eligible') is True,
        'risk_review_immutable': review.get('immutable') is True and bool(review.get('integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Closed-disclosure record retention blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    evidence = _evidence_payload(archive, closure, review)
    data = {
        **evidence,
        'retention_days': payload.retention_days,
        'retention_expires_at': (now + timedelta(days=payload.retention_days)).isoformat(),
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    record = {
        'record_id': str(uuid4()),
        **data,
        'record_state': 'retained-closed-disclosure-record',
        'baseline_evidence_hash': _hash(evidence),
        'record_integrity_hash': _hash(data),
        'audit_count': 0,
        'revalidation_count': 0,
        'immutable': True,
        'retained_by': payload.actor,
        'retained_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _record_store[payload.archive_id] = record
    return {'state': 'telegram-closed-disclosure-record-retained', 'record': record, 'external_calls_made': 0}


@router.post('/integrity/audit')
def audit_closed_disclosure_integrity(payload: ClosedDisclosureIntegrityAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit closed-disclosure integrity audit required')
    record = _record_by_id(payload.record_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram closed-disclosure record not found')
    archive = _archive_by_id(record['archive_id'])
    closure = _closure_for_archive(record['archive_id'])
    review = _review_for_archive(record['archive_id'])
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    if archive is None or closure is None or review is None:
        evidence = {}
    else:
        evidence = _evidence_payload(archive, closure, review)
    due_at = datetime.fromisoformat(record['next_audit_due_at'])
    checks = {
        'evidence_present': bool(evidence),
        'evidence_hash_unchanged': bool(evidence) and _hash(evidence) == record['baseline_evidence_hash'],
        'archive_still_closed': bool(archive and archive.get('archive_state') == 'archived-final-lifecycle-closed'),
        'closure_still_final': bool(closure and closure.get('closure_state') == 'final-disclosure-lifecycle-closed'),
        'risk_still_acceptable': bool(review and review.get('closure_eligible') is True),
        'record_not_reopened': record.get('record_state') != 'compliance-case-reopened',
    }
    drift_detected = not all(checks.values())
    sequence = record['audit_count'] + 1
    audit_data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'sequence': sequence,
        'checks': checks,
        'drift_detected': drift_detected,
        'audit_was_due': audited_at >= due_at,
        'observed_evidence_hash': _hash(evidence) if evidence else None,
        'baseline_evidence_hash': record['baseline_evidence_hash'],
    }
    audit = {
        'audit_id': str(uuid4()),
        **audit_data,
        'audit_state': 'integrity-drift-detected' if drift_detected else 'closed-record-integrity-verified',
        'integrity_hash': _hash(audit_data),
        'immutable': True,
        'audited_by': payload.actor,
        'audited_at': audited_at.isoformat(),
        'external_calls_made': 0,
    }
    _audit_store.setdefault(record['record_id'], []).append(audit)
    record.update(
        audit_count=sequence,
        last_audit_id=audit['audit_id'],
        last_audited_at=audited_at.isoformat(),
        latest_audit_checks=checks,
        record_state='integrity-drift-reopen-required' if drift_detected else 'integrity-verified-revalidation-due',
        next_audit_due_at=(audited_at + timedelta(days=record['audit_interval_days'])).isoformat(),
    )
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'record': record, 'external_calls_made': 0}


@router.post('/closure/revalidate')
def revalidate_lifecycle_closure(payload: ClosureRevalidationRequest) -> dict:
    if payload.revalidation_phrase != _REVALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit lifecycle-closure revalidation required')
    record = _record_by_id(payload.record_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram closed-disclosure record not found')
    audits = _audit_store.get(record['record_id'], [])
    if not audits:
        raise HTTPException(status_code=409, detail='Successful periodic integrity audit required before revalidation')
    latest = audits[-1]
    reopen = _reopen_store.get(record['record_id'])
    checks = {
        'latest_audit_clean': latest.get('audit_state') == 'closed-record-integrity-verified',
        'latest_audit_immutable': latest.get('immutable') is True and bool(latest.get('integrity_hash')),
        'no_open_reopened_case': not bool(reopen and reopen.get('reopen_state') == 'compliance-case-reopened'),
        'record_integrity_present': record.get('immutable') is True and bool(record.get('record_integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Lifecycle-closure revalidation blocked', 'blockers': blockers})
    sequence = record['revalidation_count'] + 1
    data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'latest_audit_id': latest['audit_id'],
        'sequence': sequence,
        'revalidation_reference': payload.revalidation_reference,
        'checks': checks,
    }
    revalidation = {
        'revalidation_id': str(uuid4()),
        **data,
        'revalidation_state': 'final-lifecycle-closure-revalidated',
        'integrity_hash': _hash(data),
        'immutable': True,
        'revalidated_by': payload.actor,
        'revalidated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _revalidation_store.setdefault(record['record_id'], []).append(revalidation)
    record.update(
        revalidation_count=sequence,
        last_revalidation_id=revalidation['revalidation_id'],
        record_state='retained-closed-disclosure-record',
    )
    return {'state': 'telegram-disclosure-lifecycle-closure-revalidated', 'revalidation': revalidation, 'record': record, 'external_calls_made': 0}


@router.post('/compliance/reopen')
def reopen_compliance_case(payload: ComplianceCaseReopenRequest) -> dict:
    if payload.reopen_phrase != _REOPEN_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit disclosure compliance-case reopening required')
    record = _record_by_id(payload.record_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram closed-disclosure record not found')
    existing = _reopen_store.get(record['record_id'])
    if existing is not None:
        return {'state': 'telegram-disclosure-compliance-case-already-reopened', 'reopen': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audits = _audit_store.get(record['record_id'], [])
    latest = audits[-1] if audits else None
    if latest is None or latest.get('audit_state') != 'integrity-drift-detected':
        raise HTTPException(status_code=409, detail='Detected integrity drift required before compliance-case reopening')
    data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'trigger_audit_id': latest['audit_id'],
        'severity': payload.severity,
        'reason': payload.reason,
    }
    reopen = {
        'reopen_id': str(uuid4()),
        **data,
        'reopen_state': 'compliance-case-reopened',
        'integrity_hash': _hash(data),
        'immutable': True,
        'reopened_by': payload.actor,
        'reopened_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _reopen_store[record['record_id']] = reopen
    record['record_state'] = 'compliance-case-reopened'
    return {'state': 'telegram-disclosure-compliance-case-reopened', 'reopen': reopen, 'record': record, 'external_calls_made': 0, 'next_layer': 'closed-record-remediation-and-reclosure-governance'}


@router.get('/status')
def closed_record_integrity_status() -> dict:
    records = list(_record_store.values())
    return {
        'retained_records': len(records),
        'integrity_audits': sum(len(items) for items in _audit_store.values()),
        'closure_revalidations': sum(len(items) for items in _revalidation_store.values()),
        'reopened_cases': len(_reopen_store),
        'drift_required': sum(1 for item in records if item.get('record_state') == 'integrity-drift-reopen-required'),
        'external_calls_made': 0,
        'mode': 'closed-record-retention-periodic-integrity-audit-closure-revalidation-reopen-governance',
    }


@router.get('/records')
def list_closed_records() -> dict:
    return {'count': len(_record_store), 'items': list(_record_store.values()), 'external_calls_made': 0}


@router.get('/audits')
def list_integrity_audits() -> dict:
    items = [item for audits in _audit_store.values() for item in audits]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/revalidations')
def list_revalidations() -> dict:
    items = [item for revalidations in _revalidation_store.values() for item in revalidations]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/reopened-cases')
def list_reopened_cases() -> dict:
    return {'count': len(_reopen_store), 'items': list(_reopen_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_post_offboarding_closure_v21_346 import command_center as v21_346_command_center
    return v21_346_command_center().replace('v21.346', 'v21.347').replace(
        'AURON TELEGRAM POST OFFBOARDING CLOSURE COMMAND CENTER',
        'AURON TELEGRAM CLOSED RECORD INTEGRITY COMMAND CENTER',
    )
