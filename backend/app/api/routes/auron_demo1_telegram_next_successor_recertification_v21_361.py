from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_next_successor_monitoring_v21_360 import (
    _audit_store,
    _drift_store,
    _monitoring_store,
)
from app.api.routes.auron_demo1_telegram_expired_renewed_successor_restoration_v21_358 import _succession_store
from app.api.routes.auron_demo1_telegram_renewed_successor_continuity_v21_357 import _continuity_store

router = APIRouter(prefix='/auron/demo1/v21.361', tags=['auron-demo1-telegram-next-successor-recertification'])
_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}
_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM NEXT SUCCESSOR DRIFT REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM NEXT SUCCESSOR SUCCESSION'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM NEXT SUCCESSOR ASSURANCE BASELINE'


class DriftRemediationValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    validation_reference: str = Field(min_length=1, max_length=300)
    validation_statement: str = Field(min_length=1, max_length=1800)


class SuccessionRecertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    recertification_phrase: str = Field(min_length=1, max_length=320)
    recertification_reference: str = Field(min_length=1, max_length=300)
    recertification_statement: str = Field(min_length=1, max_length=1800)


class RenewedBaselineRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    baseline_reference: str = Field(min_length=1, max_length=300)
    audit_interval_days: int = Field(default=90, ge=1, le=3650)


def reset_telegram_next_successor_recertification_store() -> None:
    _validation_store.clear()
    _recertification_store.clear()
    _baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


@router.post('/drift-remediation/validate')
def validate_drift_remediation(payload: DriftRemediationValidationRequest) -> dict:
    if payload.validation_phrase != _VALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit next-successor drift-remediation validation required')
    existing = _validation_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-next-successor-remediation-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    if monitoring is None or drift is None:
        raise HTTPException(status_code=404, detail='Resolved next-successor drift not found')
    audits = _audit_store.get(payload.monitoring_id, [])
    trigger = next((item for item in reversed(audits) if item.get('audit_state') == 'next-successor-drift-detected'), None)
    checks = {
        'drift_resolved': drift.get('drift_state') == 'next-successor-drift-resolved',
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
        'trigger_audit_present': trigger is not None,
        'corrected_hash_active': payload.observed_successor_hash == drift.get('corrected_successor_hash') == monitoring.get('next_successor_hash'),
        'continuity_healthy': payload.continuity_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Next-successor remediation validation blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'drift_id': drift['drift_id'],
        'trigger_audit_id': trigger['audit_id'],
        'validated_successor_hash': payload.observed_successor_hash,
        'validation_reference': payload.validation_reference,
        'validation_statement': payload.validation_statement,
        'checks': checks,
    }
    validation = {'validation_id': str(uuid4()), **data, 'validation_state': 'next-successor-drift-remediation-validated', 'integrity_hash': _hash(data), 'immutable': True, 'validated_by': payload.actor, 'validated_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _validation_store[payload.monitoring_id] = validation
    monitoring['monitoring_state'] = 'next-successor-remediation-validated-recertification-required'
    return {'state': 'telegram-next-successor-remediation-validated', 'validation': validation, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/succession/recertify')
def recertify_succession(payload: SuccessionRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit next-successor succession recertification required')
    existing = _recertification_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-next-successor-succession-already-recertified', 'recertification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    if monitoring is None or validation is None or drift is None:
        raise HTTPException(status_code=409, detail='Completed next-successor remediation validation required')
    checks = {
        'validation_complete': validation.get('validation_state') == 'next-successor-drift-remediation-validated',
        'validation_immutable': validation.get('immutable') is True and bool(validation.get('integrity_hash')),
        'drift_resolved': drift.get('drift_state') == 'next-successor-drift-resolved',
        'validated_hash_active': validation.get('validated_successor_hash') == monitoring.get('next_successor_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Next-successor recertification blocked', 'blockers': blockers})
    data = {'monitoring_id': monitoring['monitoring_id'], 'succession_id': monitoring['succession_id'], 'validation_id': validation['validation_id'], 'validated_successor_hash': validation['validated_successor_hash'], 'recertification_reference': payload.recertification_reference, 'recertification_statement': payload.recertification_statement, 'checks': checks}
    recertification = {'recertification_id': str(uuid4()), **data, 'recertification_state': 'next-successor-succession-recertified', 'integrity_hash': _hash(data), 'immutable': True, 'recertified_by': payload.actor, 'recertified_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _recertification_store[payload.monitoring_id] = recertification
    monitoring['monitoring_state'] = 'next-successor-recertified-awaiting-renewed-baseline'
    return {'state': 'telegram-next-successor-succession-recertified', 'recertification': recertification, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/baseline/renew')
def renew_baseline(payload: RenewedBaselineRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed next-successor baseline approval required')
    existing = _baseline_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-renewed-next-successor-baseline-already-established', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    recertification = _recertification_store.get(payload.monitoring_id)
    if monitoring is None or validation is None or recertification is None:
        raise HTTPException(status_code=409, detail='Completed next-successor recertification required')
    succession = next((item for item in _succession_store.values() if item.get('succession_id') == monitoring.get('succession_id')), None)
    continuity = next((item for item in _continuity_store.values() if item.get('continuity_id') == monitoring.get('continuity_id')), None)
    checks = {
        'recertification_complete': recertification.get('recertification_state') == 'next-successor-succession-recertified',
        'recertification_immutable': recertification.get('immutable') is True and bool(recertification.get('integrity_hash')),
        'validated_hash_active': validation.get('validated_successor_hash') == monitoring.get('next_successor_hash'),
        'monitoring_awaiting_baseline': monitoring.get('monitoring_state') == 'next-successor-recertified-awaiting-renewed-baseline',
        'succession_present': succession is not None,
        'continuity_present': continuity is not None,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed next-successor baseline blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {'monitoring_id': monitoring['monitoring_id'], 'recertification_id': recertification['recertification_id'], 'previous_monitoring_hash': monitoring.get('integrity_hash'), 'active_successor_hash': monitoring['next_successor_hash'], 'baseline_reference': payload.baseline_reference, 'audit_interval_days': payload.audit_interval_days, 'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(), 'checks': checks}
    baseline = {'baseline_id': str(uuid4()), **data, 'baseline_state': 'renewed-next-successor-assurance-baseline-active', 'baseline_hash': _hash(data), 'immutable': True, 'renewed_by': payload.actor, 'renewed_at': now.isoformat(), 'external_calls_made': 0}
    _baseline_store[payload.monitoring_id] = baseline
    monitoring.update(monitoring_state='certified-next-successor-monitoring-active', superseded_integrity_hash=monitoring.get('integrity_hash'), integrity_hash=baseline['baseline_hash'], audit_interval_days=payload.audit_interval_days, next_audit_due_at=baseline['next_audit_due_at'], last_next_successor_recertification_id=recertification['recertification_id'], renewed_next_successor_baseline_id=baseline['baseline_id'])
    if succession is not None:
        succession.update(succession_state='next-successor-baseline-recertified-stable', next_successor_hash=monitoring['next_successor_hash'], last_recertification_id=recertification['recertification_id'])
    if continuity is not None:
        continuity.update(continuity_state='renewed-successor-continuity-active', active_baseline_hash=monitoring['next_successor_hash'])
    return {'state': 'telegram-renewed-next-successor-baseline-established', 'baseline': baseline, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'renewed-next-successor-continuity-monitoring'}


@router.get('/status')
def status() -> dict:
    return {'drift_remediation_validations': len(_validation_store), 'succession_recertifications': len(_recertification_store), 'renewed_next_successor_baselines': len(_baseline_store), 'external_calls_made': 0, 'mode': 'next-successor-remediation-validation-recertification-renewed-baseline-governance'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_next_successor_monitoring_v21_360 import command_center as previous
    return previous().replace('v21.360', 'v21.361').replace('AURON TELEGRAM NEXT SUCCESSOR MONITORING COMMAND CENTER', 'AURON TELEGRAM NEXT SUCCESSOR RECERTIFICATION COMMAND CENTER')
