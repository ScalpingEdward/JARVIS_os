from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_certified_reclosure_assurance_v21_350 import (
    _assurance_store,
    _audit_store,
    _drift_store,
)

router = APIRouter(prefix='/auron/demo1/v21.351', tags=['auron-demo1-telegram-assurance-recertification'])

_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}
_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM ASSURANCE DRIFT REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM CERTIFIED RECLOSURE ASSURANCE'
_RENEW_BASELINE_PHRASE = 'RENEW AURON TELEGRAM ASSURANCE BASELINE'


class DriftRemediationValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    assurance_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    validation_reference: str = Field(min_length=1, max_length=300)
    validation_statement: str = Field(min_length=1, max_length=1800)
    observed_evidence_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')


class AssuranceRecertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    assurance_id: str = Field(min_length=1, max_length=160)
    recertification_phrase: str = Field(min_length=1, max_length=320)
    recertification_reference: str = Field(min_length=1, max_length=300)
    recertification_statement: str = Field(min_length=1, max_length=1800)


class RenewedAssuranceBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    assurance_id: str = Field(min_length=1, max_length=160)
    baseline_phrase: str = Field(min_length=1, max_length=320)
    baseline_reference: str = Field(min_length=1, max_length=300)
    audit_interval_days: int = Field(default=90, ge=1, le=3650)


def reset_telegram_assurance_recertification_store() -> None:
    _validation_store.clear()
    _recertification_store.clear()
    _baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _assurance_by_id(assurance_id: str) -> dict | None:
    return next((item for item in _assurance_store.values() if item.get('assurance_id') == assurance_id), None)


@router.post('/drift-remediation/validate')
def validate_drift_remediation(payload: DriftRemediationValidationRequest) -> dict:
    if payload.validation_phrase != _VALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit assurance drift-remediation validation required')
    existing = _validation_store.get(payload.assurance_id)
    if existing is not None:
        return {'state': 'telegram-assurance-drift-remediation-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    assurance = _assurance_by_id(payload.assurance_id)
    drift = _drift_store.get(payload.assurance_id)
    if assurance is None or drift is None:
        raise HTTPException(status_code=404, detail='Resolved assurance certification drift not found')
    audits = _audit_store.get(payload.assurance_id, [])
    trigger_audit = next((item for item in reversed(audits) if item.get('audit_state') == 'reclosure-certification-drift-detected'), None)
    checks = {
        'drift_resolved': drift.get('drift_state') == 'certification-drift-resolved',
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
        'trigger_audit_present': trigger_audit is not None,
        'observed_hash_matches_resolved_hash': payload.observed_evidence_hash == drift.get('corrected_evidence_hash'),
        'control_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Drift-remediation validation blocked', 'blockers': blockers})
    data = {
        'assurance_id': assurance['assurance_id'],
        'certification_id': assurance['certification_id'],
        'drift_id': drift['drift_id'],
        'trigger_audit_id': trigger_audit['audit_id'],
        'validated_evidence_hash': payload.observed_evidence_hash,
        'validation_reference': payload.validation_reference,
        'validation_statement': payload.validation_statement,
        'checks': checks,
    }
    validation = {
        'validation_id': str(uuid4()),
        **data,
        'validation_state': 'assurance-drift-remediation-validated',
        'integrity_hash': _hash(data),
        'immutable': True,
        'validated_by': payload.actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _validation_store[payload.assurance_id] = validation
    assurance['assurance_state'] = 'drift-remediation-validated-recertification-required'
    return {'state': 'telegram-assurance-drift-remediation-validated', 'validation': validation, 'assurance': assurance, 'external_calls_made': 0}


@router.post('/recertify')
def recertify_assurance(payload: AssuranceRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certified reclosure assurance recertification required')
    existing = _recertification_store.get(payload.assurance_id)
    if existing is not None:
        return {'state': 'telegram-certified-reclosure-assurance-already-recertified', 'recertification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    assurance = _assurance_by_id(payload.assurance_id)
    validation = _validation_store.get(payload.assurance_id)
    drift = _drift_store.get(payload.assurance_id)
    if assurance is None or validation is None or drift is None:
        raise HTTPException(status_code=409, detail='Completed drift-remediation validation required before recertification')
    checks = {
        'validation_complete': validation.get('validation_state') == 'assurance-drift-remediation-validated',
        'validation_immutable': validation.get('immutable') is True and bool(validation.get('integrity_hash')),
        'drift_resolved': drift.get('drift_state') == 'certification-drift-resolved',
        'validated_hash_is_active': validation.get('validated_evidence_hash') == assurance.get('corrected_evidence_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Assurance recertification blocked', 'blockers': blockers})
    data = {
        'assurance_id': assurance['assurance_id'],
        'certification_id': assurance['certification_id'],
        'validation_id': validation['validation_id'],
        'validated_evidence_hash': validation['validated_evidence_hash'],
        'recertification_reference': payload.recertification_reference,
        'recertification_statement': payload.recertification_statement,
        'checks': checks,
    }
    recertification = {
        'recertification_id': str(uuid4()),
        **data,
        'recertification_state': 'certified-reclosure-assurance-recertified',
        'integrity_hash': _hash(data),
        'immutable': True,
        'recertified_by': payload.actor,
        'recertified_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _recertification_store[payload.assurance_id] = recertification
    assurance['assurance_state'] = 'recertified-awaiting-renewed-baseline'
    return {'state': 'telegram-certified-reclosure-assurance-recertified', 'recertification': recertification, 'assurance': assurance, 'external_calls_made': 0}


@router.post('/baseline/renew')
def renew_assurance_baseline(payload: RenewedAssuranceBaselineRequest) -> dict:
    if payload.baseline_phrase != _RENEW_BASELINE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed assurance baseline approval required')
    existing = _baseline_store.get(payload.assurance_id)
    if existing is not None:
        return {'state': 'telegram-renewed-assurance-baseline-already-established', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    assurance = _assurance_by_id(payload.assurance_id)
    recertification = _recertification_store.get(payload.assurance_id)
    validation = _validation_store.get(payload.assurance_id)
    if assurance is None or recertification is None or validation is None:
        raise HTTPException(status_code=409, detail='Completed assurance recertification required before baseline renewal')
    checks = {
        'recertification_complete': recertification.get('recertification_state') == 'certified-reclosure-assurance-recertified',
        'recertification_immutable': recertification.get('immutable') is True and bool(recertification.get('integrity_hash')),
        'validation_hash_matches_assurance': validation.get('validated_evidence_hash') == assurance.get('corrected_evidence_hash'),
        'assurance_awaiting_baseline': assurance.get('assurance_state') == 'recertified-awaiting-renewed-baseline',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed assurance baseline blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'assurance_id': assurance['assurance_id'],
        'recertification_id': recertification['recertification_id'],
        'previous_baseline_hash': assurance['baseline_hash'],
        'active_evidence_hash': assurance['corrected_evidence_hash'],
        'baseline_reference': payload.baseline_reference,
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    baseline = {
        'baseline_id': str(uuid4()),
        **data,
        'baseline_state': 'renewed-assurance-baseline-active',
        'baseline_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _baseline_store[payload.assurance_id] = baseline
    assurance.update(
        assurance_state='certified-reclosure-long-term-assurance-active',
        superseded_baseline_hash=assurance['baseline_hash'],
        baseline_hash=baseline['baseline_hash'],
        audit_interval_days=payload.audit_interval_days,
        next_audit_due_at=baseline['next_audit_due_at'],
        last_recertification_id=recertification['recertification_id'],
        renewed_baseline_id=baseline['baseline_id'],
    )
    return {'state': 'telegram-renewed-assurance-baseline-established', 'baseline': baseline, 'assurance': assurance, 'external_calls_made': 0, 'next_layer': 'renewed-assurance-continuity-and-recertification-monitoring'}


@router.get('/status')
def assurance_recertification_status() -> dict:
    return {
        'drift_remediation_validations': len(_validation_store),
        'assurance_recertifications': len(_recertification_store),
        'renewed_assurance_baselines': len(_baseline_store),
        'external_calls_made': 0,
        'mode': 'assurance-recertification-drift-remediation-validation-renewed-baseline-governance',
    }


@router.get('/validations')
def list_validations() -> dict:
    return {'count': len(_validation_store), 'items': list(_validation_store.values()), 'external_calls_made': 0}


@router.get('/recertifications')
def list_recertifications() -> dict:
    return {'count': len(_recertification_store), 'items': list(_recertification_store.values()), 'external_calls_made': 0}


@router.get('/baselines')
def list_baselines() -> dict:
    return {'count': len(_baseline_store), 'items': list(_baseline_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_certified_reclosure_assurance_v21_350 import command_center as v21_350_command_center
    return v21_350_command_center().replace('v21.350', 'v21.351').replace(
        'AURON TELEGRAM CERTIFIED RECLOSURE ASSURANCE COMMAND CENTER',
        'AURON TELEGRAM ASSURANCE RECERTIFICATION COMMAND CENTER',
    )
