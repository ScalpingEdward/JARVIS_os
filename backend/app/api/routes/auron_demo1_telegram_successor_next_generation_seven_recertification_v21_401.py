from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_seven_monitoring_v21_400 import (
    _audit_store,
    _drift_store,
    _monitoring_store,
    _resolution_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.401',
    tags=['auron-demo1-telegram-successor-next-generation-seven-recertification'],
)

_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}

_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN DRIFT REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN SUCCESSION'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN ASSURANCE BASELINE'


class RemediationValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    drift_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    observed_corrected_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    validation_reference: str = Field(min_length=1, max_length=300)
    validation_statement: str = Field(min_length=1, max_length=1800)


class SuccessionRecertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    validation_id: str = Field(min_length=1, max_length=160)
    recertification_phrase: str = Field(min_length=1, max_length=320)
    recertification_reference: str = Field(min_length=1, max_length=300)
    recertification_statement: str = Field(min_length=1, max_length=1800)


class RenewedBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    recertification_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    renewed_successor_next_generation_seven_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    audit_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)
    renewal_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_successor_next_generation_seven_recertification_store() -> None:
    _validation_store.clear()
    _recertification_store.clear()
    _baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _validation_by_id(validation_id: str) -> dict | None:
    return next((item for item in _validation_store.values() if item.get('validation_id') == validation_id), None)


def _recertification_by_id(recertification_id: str) -> dict | None:
    return next((item for item in _recertification_store.values() if item.get('recertification_id') == recertification_id), None)


@router.post('/remediation/validate')
def validate_remediation(payload: RemediationValidationRequest) -> dict:
    if payload.validation_phrase != _VALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven remediation validation required')
    existing = _validation_store.get(payload.drift_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-seven-remediation-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    drift = next((item for item in _drift_store.values() if item.get('drift_id') == payload.drift_id), None)
    resolution = _resolution_store.get(payload.drift_id)
    if monitoring is None or drift is None or resolution is None:
        raise HTTPException(status_code=409, detail='Resolved v21.400 drift evidence required')
    trigger_audit = next((item for item in _audit_store.get(monitoring['monitoring_id'], []) if item.get('audit_id') == drift.get('trigger_audit_id')), None)
    expected_hash = monitoring.get('active_successor_next_generation_seven_hash')
    checks = {
        'drift_resolved': drift.get('drift_state') == 'successor-next-generation-seven-drift-resolved',
        'resolution_immutable': resolution.get('immutable') is True and bool(resolution.get('integrity_hash')),
        'failed_trigger_audit': trigger_audit is not None and trigger_audit.get('healthy') is False,
        'corrected_hash_matches': payload.observed_corrected_hash == expected_hash == resolution.get('corrected_hash'),
        'controls_healthy': payload.control_state == 'healthy',
        'monitoring_requires_recertification': monitoring.get('monitoring_state') == 'successor-next-generation-seven-drift-resolved-recertification-required',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Remediation validation blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'drift_id': drift['drift_id'],
        'resolution_id': resolution['resolution_id'],
        'trigger_audit_id': trigger_audit['audit_id'],
        'corrected_hash': payload.observed_corrected_hash,
        'validation_reference': payload.validation_reference,
        'validation_statement': payload.validation_statement,
        'checks': checks,
    }
    validation = {
        'validation_id': str(uuid4()),
        **data,
        'validation_state': 'successor-next-generation-seven-remediation-validated',
        'integrity_hash': _hash(data),
        'immutable': True,
        'validated_by': payload.actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _validation_store[payload.drift_id] = validation
    return {'state': 'telegram-successor-next-generation-seven-remediation-validated', 'validation': validation, 'external_calls_made': 0}


@router.post('/succession/recertify')
def recertify_succession(payload: SuccessionRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven succession recertification required')
    validation = _validation_by_id(payload.validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail='Validated remediation evidence required')
    existing = _recertification_store.get(validation['validation_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-seven-succession-already-recertified', 'recertification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if validation.get('validation_state') != 'successor-next-generation-seven-remediation-validated' or validation.get('immutable') is not True:
        raise HTTPException(status_code=409, detail='Immutable completed validation required')
    data = {
        'validation_id': validation['validation_id'],
        'monitoring_id': validation['monitoring_id'],
        'corrected_hash': validation['corrected_hash'],
        'recertification_reference': payload.recertification_reference,
        'recertification_statement': payload.recertification_statement,
    }
    recertification = {
        'recertification_id': str(uuid4()),
        **data,
        'recertification_state': 'successor-next-generation-seven-succession-recertified',
        'integrity_hash': _hash(data),
        'immutable': True,
        'recertified_by': payload.actor,
        'recertified_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _recertification_store[validation['validation_id']] = recertification
    return {'state': 'telegram-successor-next-generation-seven-succession-recertified', 'recertification': recertification, 'external_calls_made': 0}


@router.post('/baseline/renew')
def renew_baseline(payload: RenewedBaselineRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-seven assurance baseline renewal required')
    recertification = _recertification_by_id(payload.recertification_id)
    if recertification is None:
        raise HTTPException(status_code=404, detail='Succession recertification required')
    monitoring_id = recertification['monitoring_id']
    existing = _baseline_store.get(monitoring_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-seven-baseline-already-renewed', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(monitoring_id)
    if monitoring is None or recertification.get('immutable') is not True:
        raise HTTPException(status_code=409, detail='Monitoring and immutable recertification evidence required')
    superseded_hash = monitoring['active_successor_next_generation_seven_hash']
    if payload.renewed_successor_next_generation_seven_hash == superseded_hash:
        raise HTTPException(status_code=409, detail='Renewed baseline hash must differ from superseded hash')
    now = datetime.now(timezone.utc)
    data = {
        'monitoring_id': monitoring_id,
        'recertification_id': recertification['recertification_id'],
        'superseded_successor_next_generation_seven_hash': superseded_hash,
        'renewed_successor_next_generation_seven_hash': payload.renewed_successor_next_generation_seven_hash,
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(),
        'renewal_reference': payload.renewal_reference,
    }
    baseline = {
        'baseline_id': str(uuid4()),
        **data,
        'baseline_state': 'renewed-successor-next-generation-seven-baseline-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _baseline_store[monitoring_id] = baseline
    monitoring.update(
        active_successor_next_generation_seven_hash=payload.renewed_successor_next_generation_seven_hash,
        monitoring_state='renewed-successor-next-generation-seven-monitoring-active',
        next_audit_due_at=data['next_audit_due_at'],
        open_drift_id=None,
    )
    return {
        'state': 'telegram-renewed-successor-next-generation-seven-baseline-active',
        'baseline': baseline,
        'monitoring': monitoring,
        'external_calls_made': 0,
        'next_layer': 'renewed-successor-next-generation-seven-continuity-health-expiry-governance',
    }


@router.get('/status')
def status() -> dict:
    return {
        'validations': len(_validation_store),
        'recertifications': len(_recertification_store),
        'renewed_baselines': len(_baseline_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-seven-remediation-validation-recertification-renewed-baseline-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.401</title></head><body><h1>AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN RECERTIFICATION COMMAND CENTER</h1><p>Drift-remediation validation, succession recertification and renewed baseline governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
