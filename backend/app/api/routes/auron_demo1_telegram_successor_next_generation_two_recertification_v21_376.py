from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_two_monitoring_v21_375 import (
    _audit_store,
    _drift_store,
    _monitoring_store,
    _resolution_store,
)
from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_restoration_v21_373 import (
    _succession_store,
)
from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_continuity_v21_372 import (
    _continuity_monitor_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.376',
    tags=['auron-demo1-telegram-successor-next-generation-two-recertification'],
)

_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}

_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO DRIFT REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO SUCCESSION'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO ASSURANCE BASELINE'


class RemediationValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    observed_corrected_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
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
    renewed_baseline_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    baseline_reference: str = Field(min_length=1, max_length=300)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)


def reset_telegram_successor_next_generation_two_recertification_store() -> None:
    _validation_store.clear()
    _recertification_store.clear()
    _baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _continuity_record(continuity_monitor_id: str) -> dict | None:
    return next(
        (item for item in _continuity_monitor_store.values() if item.get('continuity_monitor_id') == continuity_monitor_id),
        None,
    )


@router.post('/remediation/validate')
def validate_remediation(payload: RemediationValidationRequest) -> dict:
    if payload.validation_phrase != _VALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-two remediation validation required')
    existing = _validation_store.get(payload.monitoring_id)
    if existing is not None:
        return {
            'state': 'telegram-successor-next-generation-two-remediation-already-validated',
            'validation': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Successor-next-generation-two monitoring not found')
    drift = _drift_store.get(payload.monitoring_id)
    resolution = _resolution_store.get(payload.monitoring_id)
    if drift is None or resolution is None:
        raise HTTPException(status_code=409, detail='Resolved successor-next-generation-two drift required')
    trigger_audit = next(
        (item for item in _audit_store.get(payload.monitoring_id, []) if item.get('audit_id') == drift.get('trigger_audit_id')),
        None,
    )
    corrected_hash = resolution.get('corrected_hash')
    checks = {
        'drift_resolved': drift.get('drift_state') == 'successor-next-generation-two-drift-resolved',
        'drift_immutable': drift.get('immutable') is True and bool(drift.get('integrity_hash')),
        'resolution_complete': resolution.get('resolution_state')
        == 'successor-next-generation-two-drift-resolved-awaiting-recertification',
        'resolution_immutable': resolution.get('immutable') is True and bool(resolution.get('integrity_hash')),
        'trigger_audit_failed': trigger_audit is not None and trigger_audit.get('healthy') is False,
        'corrected_hash_matches': bool(corrected_hash) and payload.observed_corrected_hash == corrected_hash,
        'controls_healthy': payload.control_state == 'healthy',
        'monitoring_requires_recertification': monitoring.get('monitoring_state')
        == 'successor-next-generation-two-recertification-required',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(
            status_code=409,
            detail={'message': 'Successor-next-generation-two remediation validation blocked', 'blockers': blockers},
        )
    data = {
        'monitoring_id': payload.monitoring_id,
        'continuity_monitor_id': monitoring['continuity_monitor_id'],
        'drift_id': drift['drift_id'],
        'resolution_id': resolution['resolution_id'],
        'trigger_audit_id': drift['trigger_audit_id'],
        'corrected_hash': corrected_hash,
        'validation_reference': payload.validation_reference,
        'validation_statement': payload.validation_statement,
        'checks': checks,
    }
    validation = {
        'validation_id': str(uuid4()),
        **data,
        'validation_state': 'successor-next-generation-two-remediation-validated',
        'integrity_hash': _hash(data),
        'immutable': True,
        'validated_by': payload.actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _validation_store[payload.monitoring_id] = validation
    monitoring['monitoring_state'] = 'successor-next-generation-two-remediation-validated-awaiting-recertification'
    return {
        'state': 'telegram-successor-next-generation-two-remediation-validated',
        'validation': validation,
        'monitoring': monitoring,
        'external_calls_made': 0,
    }


@router.post('/succession/recertify')
def recertify_succession(payload: SuccessionRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-two succession recertification required')
    existing = _recertification_store.get(payload.monitoring_id)
    if existing is not None:
        return {
            'state': 'telegram-successor-next-generation-two-succession-already-recertified',
            'recertification': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }
    monitoring = _monitoring_by_id(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    if monitoring is None or validation is None:
        raise HTTPException(status_code=409, detail='Completed remediation validation required before recertification')
    checks = {
        'validation_complete': validation.get('validation_state') == 'successor-next-generation-two-remediation-validated',
        'validation_immutable': validation.get('immutable') is True and bool(validation.get('integrity_hash')),
        'monitoring_ready': monitoring.get('monitoring_state')
        == 'successor-next-generation-two-remediation-validated-awaiting-recertification',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Recertification blocked', 'blockers': blockers})
    data = {
        'monitoring_id': payload.monitoring_id,
        'continuity_monitor_id': monitoring['continuity_monitor_id'],
        'validation_id': validation['validation_id'],
        'corrected_hash': validation['corrected_hash'],
        'recertification_reference': payload.recertification_reference,
        'recertification_statement': payload.recertification_statement,
        'checks': checks,
    }
    recertification = {
        'recertification_id': str(uuid4()),
        **data,
        'recertification_state': 'successor-next-generation-two-succession-recertified',
        'integrity_hash': _hash(data),
        'immutable': True,
        'recertified_by': payload.actor,
        'recertified_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _recertification_store[payload.monitoring_id] = recertification
    monitoring['monitoring_state'] = 'successor-next-generation-two-recertified-awaiting-renewed-baseline'
    return {
        'state': 'telegram-successor-next-generation-two-succession-recertified',
        'recertification': recertification,
        'monitoring': monitoring,
        'external_calls_made': 0,
    }


@router.post('/baseline/renew')
def renew_baseline(payload: RenewedBaselineRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-two baseline renewal required')
    existing = _baseline_store.get(payload.monitoring_id)
    if existing is not None:
        return {
            'state': 'telegram-renewed-successor-next-generation-two-baseline-already-active',
            'baseline': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }
    monitoring = _monitoring_by_id(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    recertification = _recertification_store.get(payload.monitoring_id)
    if monitoring is None or validation is None or recertification is None:
        raise HTTPException(status_code=409, detail='Completed validation and recertification required before baseline renewal')
    checks = {
        'recertification_complete': recertification.get('recertification_state')
        == 'successor-next-generation-two-succession-recertified',
        'recertification_immutable': recertification.get('immutable') is True and bool(recertification.get('integrity_hash')),
        'renewed_hash_matches_validated': payload.renewed_baseline_hash == validation['corrected_hash'],
        'monitoring_ready': monitoring.get('monitoring_state')
        == 'successor-next-generation-two-recertified-awaiting-renewed-baseline',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed baseline blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    previous_hash = monitoring['active_successor_next_generation_two_hash']
    data = {
        'monitoring_id': payload.monitoring_id,
        'continuity_monitor_id': monitoring['continuity_monitor_id'],
        'validation_id': validation['validation_id'],
        'recertification_id': recertification['recertification_id'],
        'superseded_hash': previous_hash,
        'renewed_baseline_hash': payload.renewed_baseline_hash,
        'baseline_reference': payload.baseline_reference,
        'audit_interval_days': payload.audit_interval_days,
        'checks': checks,
    }
    baseline = {
        'baseline_id': str(uuid4()),
        **data,
        'baseline_state': 'renewed-successor-next-generation-two-baseline-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _baseline_store[payload.monitoring_id] = baseline
    monitoring.update(
        monitoring_state='renewed-successor-next-generation-two-monitoring-active',
        superseded_successor_next_generation_two_hash=previous_hash,
        active_successor_next_generation_two_hash=payload.renewed_baseline_hash,
        renewed_baseline_id=baseline['baseline_id'],
        audit_interval_days=payload.audit_interval_days,
        next_audit_due_at=(now + timedelta(days=payload.audit_interval_days)).isoformat(),
    )
    continuity = _continuity_record(monitoring['continuity_monitor_id'])
    if continuity is not None:
        continuity.update(
            active_baseline_hash=payload.renewed_baseline_hash,
            continuity_state='renewed-successor-next-generation-two-continuity-active',
            renewed_successor_next_generation_two_baseline_id=baseline['baseline_id'],
        )
    succession = _succession_store.get(monitoring['continuity_monitor_id'])
    if succession is not None:
        succession.update(
            succession_state='renewed-successor-next-generation-two-baseline-active',
            superseded_successor_next_generation_two_hash=previous_hash,
            successor_next_generation_two_hash=payload.renewed_baseline_hash,
            recertification_id=recertification['recertification_id'],
        )
    return {
        'state': 'telegram-renewed-successor-next-generation-two-baseline-established',
        'baseline': baseline,
        'monitoring': monitoring,
        'continuity_monitor': continuity,
        'external_calls_made': 0,
        'next_layer': 'renewed-successor-next-generation-two-continuity-and-expiry-governance',
    }


@router.get('/status')
def status() -> dict:
    return {
        'remediation_validations': len(_validation_store),
        'succession_recertifications': len(_recertification_store),
        'renewed_baselines': len(_baseline_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-two-remediation-validation-recertification-renewed-baseline-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>AURON v21.376</title></head><body><main><h1>AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO RECERTIFICATION COMMAND CENTER</h1><p>Drift-remediation validation, succession recertification and renewed-baseline governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></main></body></html>'''
