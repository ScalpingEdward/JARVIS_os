from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_post_remediation_probation_certification_v21_349 import (
    _certification_store,
    _probation_store,
)
from app.api.routes.auron_demo1_telegram_closed_record_integrity_v21_347 import _record_store

router = APIRouter(prefix='/auron/demo1/v21.350', tags=['auron-demo1-telegram-certified-reclosure-assurance'])

_assurance_store: dict[str, dict] = {}
_audit_store: dict[str, list[dict]] = {}
_drift_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM CERTIFIED RECLOSURE ASSURANCE'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM CORRECTIVE CONTROL'
_OPEN_DRIFT_PHRASE = 'OPEN AURON TELEGRAM RECLOSURE CERTIFICATION DRIFT'
_RESOLVE_DRIFT_PHRASE = 'RESOLVE AURON TELEGRAM RECLOSURE CERTIFICATION DRIFT'


class CertifiedReclosureAssuranceStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    audit_interval_days: int = Field(default=90, ge=1, le=3650)


class CorrectiveControlAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    assurance_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_evidence_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    audit_statement: str = Field(min_length=1, max_length=1800)
    audited_at: datetime | None = None


class CertificationDriftOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    assurance_id: str = Field(min_length=1, max_length=160)
    open_phrase: str = Field(min_length=1, max_length=320)
    severity: str = Field(pattern='^(low|medium|high|critical)$')
    reason: str = Field(min_length=1, max_length=1800)


class CertificationDriftResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    assurance_id: str = Field(min_length=1, max_length=160)
    resolve_phrase: str = Field(min_length=1, max_length=320)
    resolution: str = Field(min_length=1, max_length=1800)
    corrected_evidence_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')


def reset_telegram_certified_reclosure_assurance_store() -> None:
    _assurance_store.clear()
    _audit_store.clear()
    _drift_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _certification_by_id(certification_id: str) -> dict | None:
    return next((item for item in _certification_store.values() if item.get('certification_id') == certification_id), None)


def _assurance_by_id(assurance_id: str) -> dict | None:
    return next((item for item in _assurance_store.values() if item.get('assurance_id') == assurance_id), None)


def _record_by_id(record_id: str) -> dict | None:
    return next((item for item in _record_store.values() if item.get('record_id') == record_id), None)


@router.post('/assurance/start')
def start_certified_reclosure_assurance(payload: CertifiedReclosureAssuranceStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified reclosure assurance approval required')
    existing = _assurance_store.get(payload.certification_id)
    if existing is not None:
        return {'state': 'telegram-certified-reclosure-assurance-already-started', 'assurance': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certification = _certification_by_id(payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=404, detail='Governed reclosure certification not found')
    probation = _probation_store.get(certification['record_id'])
    record = _record_by_id(certification['record_id'])
    checks = {
        'certification_stable': certification.get('certification_state') == 'governed-reclosure-certified-stable',
        'certification_immutable': certification.get('immutable') is True and bool(certification.get('integrity_hash')),
        'probation_closed': bool(probation and probation.get('probation_state') == 'post-remediation-probation-certified-closed'),
        'record_closed': bool(record and record.get('record_state') == 'retained-closed-disclosure-record'),
        'evidence_hash_present': bool(certification.get('corrected_evidence_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certified reclosure assurance blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'certification_id': certification['certification_id'],
        'record_id': certification['record_id'],
        'corrected_evidence_hash': certification['corrected_evidence_hash'],
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    assurance = {
        'assurance_id': str(uuid4()),
        **data,
        'assurance_state': 'certified-reclosure-long-term-assurance-active',
        'baseline_hash': _hash(data),
        'audit_count': 0,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _assurance_store[payload.certification_id] = assurance
    return {'state': 'telegram-certified-reclosure-assurance-started', 'assurance': assurance, 'external_calls_made': 0}


@router.post('/control/audit')
def audit_corrective_control(payload: CorrectiveControlAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit corrective-control audit approval required')
    assurance = _assurance_by_id(payload.assurance_id)
    if assurance is None:
        raise HTTPException(status_code=404, detail='Certified reclosure assurance not found')
    drift = _drift_store.get(assurance['assurance_id'])
    if drift and drift.get('drift_state') == 'certification-drift-open':
        raise HTTPException(status_code=409, detail='Open certification drift blocks routine audit')
    audited_at = payload.audited_at or datetime.now(timezone.utc)
    expected_hash = assurance['corrected_evidence_hash']
    hash_matches = payload.observed_evidence_hash == expected_hash
    healthy = hash_matches and payload.control_state == 'healthy'
    sequence = assurance['audit_count'] + 1
    data = {
        'assurance_id': assurance['assurance_id'],
        'certification_id': assurance['certification_id'],
        'sequence': sequence,
        'expected_evidence_hash': expected_hash,
        'observed_evidence_hash': payload.observed_evidence_hash,
        'hash_matches': hash_matches,
        'control_state': payload.control_state,
        'healthy': healthy,
        'audit_statement': payload.audit_statement,
        'audit_was_due': audited_at >= datetime.fromisoformat(assurance['next_audit_due_at']),
    }
    audit = {
        'audit_id': str(uuid4()),
        **data,
        'audit_state': 'corrective-control-certified' if healthy else 'reclosure-certification-drift-detected',
        'integrity_hash': _hash(data),
        'immutable': True,
        'audited_by': payload.actor,
        'audited_at': audited_at.isoformat(),
        'external_calls_made': 0,
    }
    _audit_store.setdefault(assurance['assurance_id'], []).append(audit)
    assurance.update(
        audit_count=sequence,
        last_audit_id=audit['audit_id'],
        last_audited_at=audited_at.isoformat(),
        next_audit_due_at=(audited_at + timedelta(days=assurance['audit_interval_days'])).isoformat(),
        assurance_state='certified-reclosure-long-term-assurance-active' if healthy else 'certification-drift-governance-required',
    )
    return {'state': f"telegram-{audit['audit_state']}", 'audit': audit, 'assurance': assurance, 'external_calls_made': 0}


@router.post('/drift/open')
def open_certification_drift(payload: CertificationDriftOpenRequest) -> dict:
    if payload.open_phrase != _OPEN_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certification drift opening approval required')
    assurance = _assurance_by_id(payload.assurance_id)
    if assurance is None:
        raise HTTPException(status_code=404, detail='Certified reclosure assurance not found')
    existing = _drift_store.get(assurance['assurance_id'])
    if existing and existing.get('drift_state') == 'certification-drift-open':
        return {'state': 'telegram-reclosure-certification-drift-already-open', 'drift': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audits = _audit_store.get(assurance['assurance_id'], [])
    latest = audits[-1] if audits else None
    if latest is None or latest.get('audit_state') != 'reclosure-certification-drift-detected':
        raise HTTPException(status_code=409, detail='Detected certification drift required')
    data = {
        'assurance_id': assurance['assurance_id'],
        'certification_id': assurance['certification_id'],
        'trigger_audit_id': latest['audit_id'],
        'severity': payload.severity,
        'reason': payload.reason,
    }
    drift = {
        'drift_id': str(uuid4()),
        **data,
        'drift_state': 'certification-drift-open',
        'integrity_hash': _hash(data),
        'immutable': True,
        'opened_by': payload.actor,
        'opened_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _drift_store[assurance['assurance_id']] = drift
    assurance['assurance_state'] = 'certification-drift-open'
    return {'state': 'telegram-reclosure-certification-drift-opened', 'drift': drift, 'assurance': assurance, 'external_calls_made': 0}


@router.post('/drift/resolve')
def resolve_certification_drift(payload: CertificationDriftResolveRequest) -> dict:
    if payload.resolve_phrase != _RESOLVE_DRIFT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certification drift resolution approval required')
    assurance = _assurance_by_id(payload.assurance_id)
    drift = _drift_store.get(payload.assurance_id)
    if assurance is None or drift is None:
        raise HTTPException(status_code=404, detail='Open certification drift not found')
    if drift.get('drift_state') == 'certification-drift-resolved':
        return {'state': 'telegram-reclosure-certification-drift-already-resolved', 'drift': drift, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc)
    drift.update(
        drift_state='certification-drift-resolved',
        resolution=payload.resolution,
        corrected_evidence_hash=payload.corrected_evidence_hash,
        resolved_by=payload.actor,
        resolved_at=now.isoformat(),
    )
    assurance.update(
        corrected_evidence_hash=payload.corrected_evidence_hash,
        assurance_state='certified-reclosure-long-term-assurance-active',
        next_audit_due_at=(now + timedelta(days=assurance['audit_interval_days'])).isoformat(),
    )
    return {'state': 'telegram-reclosure-certification-drift-resolved', 'drift': drift, 'assurance': assurance, 'external_calls_made': 0, 'next_layer': 'certified-reclosure-assurance-recertification-governance'}


@router.get('/status')
def certified_reclosure_assurance_status() -> dict:
    return {
        'assurance_records': len(_assurance_store),
        'corrective_control_audits': sum(len(items) for items in _audit_store.values()),
        'open_certification_drifts': sum(1 for item in _drift_store.values() if item.get('drift_state') == 'certification-drift-open'),
        'resolved_certification_drifts': sum(1 for item in _drift_store.values() if item.get('drift_state') == 'certification-drift-resolved'),
        'external_calls_made': 0,
        'mode': 'certified-reclosure-long-term-assurance-corrective-control-audit-certification-drift-governance',
    }


@router.get('/assurances')
def list_assurances() -> dict:
    return {'count': len(_assurance_store), 'items': list(_assurance_store.values()), 'external_calls_made': 0}


@router.get('/audits')
def list_audits() -> dict:
    items = [item for audits in _audit_store.values() for item in audits]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/drifts')
def list_drifts() -> dict:
    return {'count': len(_drift_store), 'items': list(_drift_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_post_remediation_probation_certification_v21_349 import command_center as v21_349_command_center
    return v21_349_command_center().replace('v21.349', 'v21.350').replace(
        'AURON TELEGRAM POST REMEDIATION PROBATION CERTIFICATION COMMAND CENTER',
        'AURON TELEGRAM CERTIFIED RECLOSURE ASSURANCE COMMAND CENTER',
    )
