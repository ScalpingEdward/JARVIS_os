from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_monitoring_v21_365 import (
    _audit_store,
    _drift_store,
    _monitoring_store,
)
from app.api.routes.auron_demo1_telegram_expired_renewed_next_successor_restoration_v21_363 import _succession_store
from app.api.routes.auron_demo1_telegram_renewed_next_successor_continuity_v21_362 import _continuity_store

router = APIRouter(prefix='/auron/demo1/v21.366', tags=['auron-demo1-telegram-successor-next-recertification'])
_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}
_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT DRIFT REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT SUCCESSION'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT ASSURANCE BASELINE'


class DriftRemediationValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
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


def reset_telegram_successor_next_recertification_store() -> None:
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
        raise HTTPException(status_code=403, detail='Explicit successor-next drift-remediation validation required')
    existing = _validation_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-remediation-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    if monitoring is None or drift is None:
        raise HTTPException(status_code=404, detail='Resolved successor-next drift not found')
    audits = _audit_store.get(payload.monitoring_id, [])
    trigger = next((item for item in reversed(audits) if item.get('audit_state') == 'successor-next-drift-detected'), None)
    checks = {
        'drift_resolved': drift.get('drift_state') == 'successor-next-drift-resolved',
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
        'trigger_audit_present': trigger is not None,
        'corrected_hash_active': payload.observed_successor_next_hash == drift.get('corrected_successor_next_hash') == monitoring.get('successor_next_hash'),
        'continuity_healthy': payload.continuity_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-next remediation validation blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'drift_id': drift['drift_id'],
        'trigger_audit_id': trigger['audit_id'],
        'validated_successor_next_hash': payload.observed_successor_next_hash,
        'validation_reference': payload.validation_reference,
        'validation_statement': payload.validation_statement,
        'checks': checks,
    }
    validation = {
        'validation_id': str(uuid4()),
        **data,
        'validation_state': 'successor-next-drift-remediation-validated',
        'integrity_hash': _hash(data),
        'immutable': True,
        'validated_by': payload.actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _validation_store[payload.monitoring_id] = validation
    monitoring['monitoring_state'] = 'successor-next-remediation-validated-recertification-required'
    return {'state': 'telegram-successor-next-remediation-validated', 'validation': validation, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/succession/recertify')
def recertify_succession(payload: SuccessionRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next succession recertification required')
    existing = _recertification_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-succession-already-recertified', 'recertification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    if monitoring is None or validation is None or drift is None:
        raise HTTPException(status_code=409, detail='Completed successor-next remediation validation required')
    checks = {
        'validation_complete': validation.get('validation_state') == 'successor-next-drift-remediation-validated',
        'validation_immutable': validation.get('immutable') is True and bool(validation.get('integrity_hash')),
        'drift_resolved': drift.get('drift_state') == 'successor-next-drift-resolved',
        'validated_hash_active': validation.get('validated_successor_next_hash') == monitoring.get('successor_next_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-next recertification blocked', 'blockers': blockers})
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'succession_id': monitoring['succession_id'],
        'validation_id': validation['validation_id'],
        'validated_successor_next_hash': validation['validated_successor_next_hash'],
        'recertification_reference': payload.recertification_reference,
        'recertification_statement': payload.recertification_statement,
        'checks': checks,
    }
    recertification = {
        'recertification_id': str(uuid4()),
        **data,
        'recertification_state': 'successor-next-succession-recertified',
        'integrity_hash': _hash(data),
        'immutable': True,
        'recertified_by': payload.actor,
        'recertified_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _recertification_store[payload.monitoring_id] = recertification
    monitoring['monitoring_state'] = 'successor-next-recertified-awaiting-renewed-baseline'
    return {'state': 'telegram-successor-next-succession-recertified', 'recertification': recertification, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/baseline/renew')
def renew_baseline(payload: RenewedBaselineRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit renewed successor-next baseline approval required')
    existing = _baseline_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-baseline-already-established', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    recertification = _recertification_store.get(payload.monitoring_id)
    if monitoring is None or validation is None or recertification is None:
        raise HTTPException(status_code=409, detail='Completed successor-next recertification required')
    succession = next((item for item in _succession_store.values() if item.get('succession_id') == monitoring.get('succession_id')), None)
    continuity = next((item for item in _continuity_store.values() if item.get('continuity_id') == monitoring.get('continuity_id')), None)
    checks = {
        'recertification_complete': recertification.get('recertification_state') == 'successor-next-succession-recertified',
        'recertification_immutable': recertification.get('immutable') is True and bool(recertification.get('integrity_hash')),
        'validated_hash_active': validation.get('validated_successor_next_hash') == monitoring.get('successor_next_hash'),
        'monitoring_awaiting_baseline': monitoring.get('monitoring_state') == 'successor-next-recertified-awaiting-renewed-baseline',
        'succession_present': succession is not None,
        'continuity_present': continuity is not None,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed successor-next baseline blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'monitoring_id': monitoring['monitoring_id'],
        'recertification_id': recertification['recertification_id'],
        'previous_monitoring_hash': monitoring.get('integrity_hash'),
        'active_successor_next_hash': monitoring['successor_next_hash'],
        'baseline_reference': payload.baseline_reference,
        'audit_interval_days': payload.audit_interval_days,
        'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(),
        'checks': checks,
    }
    baseline = {
        'baseline_id': str(uuid4()),
        **data,
        'baseline_state': 'renewed-successor-next-assurance-baseline-active',
        'baseline_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _baseline_store[payload.monitoring_id] = baseline
    monitoring.update(
        monitoring_state='certified-successor-next-monitoring-active',
        superseded_integrity_hash=monitoring.get('integrity_hash'),
        integrity_hash=baseline['baseline_hash'],
        audit_interval_days=payload.audit_interval_days,
        next_audit_due_at=baseline['next_audit_due_at'],
        last_successor_next_recertification_id=recertification['recertification_id'],
        renewed_successor_next_baseline_id=baseline['baseline_id'],
    )
    if succession is not None:
        succession.update(succession_state='successor-next-baseline-recertified-stable', successor_next_hash=monitoring['successor_next_hash'], last_recertification_id=recertification['recertification_id'])
    if continuity is not None:
        continuity.update(continuity_state='renewed-next-successor-continuity-active', active_baseline_hash=monitoring['successor_next_hash'])
    return {'state': 'telegram-renewed-successor-next-baseline-established', 'baseline': baseline, 'monitoring': monitoring, 'external_calls_made': 0, 'next_layer': 'renewed-successor-next-continuity-monitoring'}


@router.get('/status')
def status() -> dict:
    return {
        'drift_remediation_validations': len(_validation_store),
        'succession_recertifications': len(_recertification_store),
        'renewed_successor_next_baselines': len(_baseline_store),
        'external_calls_made': 0,
        'mode': 'successor-next-remediation-validation-recertification-renewed-baseline-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_successor_next_monitoring_v21_365 import command_center as previous
    return previous().replace('v21.365', 'v21.366').replace(
        'AURON TELEGRAM SUCCESSOR NEXT MONITORING COMMAND CENTER',
        'AURON TELEGRAM SUCCESSOR NEXT RECERTIFICATION COMMAND CENTER',
    )
