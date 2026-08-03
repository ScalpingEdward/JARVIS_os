from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_three_monitoring_v21_380 import (
    _audit_store,
    _drift_store,
    _monitoring_store,
    _resolution_store,
)
from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_two_restoration_v21_378 import _succession_store
from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_two_continuity_v21_377 import _continuity_monitor_store

router = APIRouter(prefix='/auron/demo1/v21.381', tags=['auron-demo1-telegram-successor-next-generation-three-recertification'])
_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}

_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE DRIFT REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE SUCCESSION'
_RENEW_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE ASSURANCE BASELINE'


class ValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    validation_reference: str = Field(min_length=1, max_length=300)
    validation_statement: str = Field(min_length=1, max_length=1800)


class RecertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    recertification_phrase: str = Field(min_length=1, max_length=320)
    recertification_reference: str = Field(min_length=1, max_length=300)
    recertification_statement: str = Field(min_length=1, max_length=1800)


class BaselineRenewalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    renewal_phrase: str = Field(min_length=1, max_length=320)
    renewed_successor_next_generation_three_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    baseline_reference: str = Field(min_length=1, max_length=300)
    audit_interval_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=365, ge=1, le=3650)


def reset_telegram_successor_next_generation_three_recertification_store() -> None:
    _validation_store.clear(); _recertification_store.clear(); _baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _monitoring(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _continuity(continuity_monitor_id: str) -> dict | None:
    return next((item for item in _continuity_monitor_store.values() if item.get('continuity_monitor_id') == continuity_monitor_id), None)


@router.post('/drift-remediation/validate')
def validate_remediation(payload: ValidationRequest) -> dict:
    if payload.validation_phrase != _VALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit drift-remediation validation required')
    existing = _validation_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-three-remediation-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring(payload.monitoring_id)
    drift = _drift_store.get(payload.monitoring_id)
    resolution = _resolution_store.get(payload.monitoring_id)
    if monitoring is None or drift is None or resolution is None:
        raise HTTPException(status_code=409, detail='Resolved v21.380 drift evidence required')
    trigger = next((a for a in _audit_store.get(payload.monitoring_id, []) if a.get('audit_id') == drift.get('trigger_audit_id')), None)
    checks = {
        'drift_resolved': drift.get('drift_state') == 'successor-next-generation-three-drift-resolved',
        'resolution_complete': resolution.get('resolution_state') == 'successor-next-generation-three-drift-resolved-awaiting-recertification',
        'resolution_immutable': resolution.get('immutable') is True and bool(resolution.get('integrity_hash')),
        'trigger_audit_failed': trigger is not None and trigger.get('healthy') is False,
        'corrected_hash_consistent': resolution.get('corrected_hash') == monitoring.get('corrected_successor_next_generation_three_hash'),
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [k for k, v in checks.items() if not v]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Remediation validation blocked', 'blockers': blockers})
    data = {'monitoring_id': payload.monitoring_id, 'drift_id': drift['drift_id'], 'resolution_id': resolution['resolution_id'], 'corrected_hash': resolution['corrected_hash'], 'validation_reference': payload.validation_reference, 'validation_statement': payload.validation_statement, 'checks': checks}
    validation = {'validation_id': str(uuid4()), **data, 'validation_state': 'successor-next-generation-three-remediation-validated', 'integrity_hash': _hash(data), 'immutable': True, 'validated_by': payload.actor, 'validated_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _validation_store[payload.monitoring_id] = validation
    return {'state': 'telegram-successor-next-generation-three-remediation-validated', 'validation': validation, 'external_calls_made': 0}


@router.post('/succession/recertify')
def recertify(payload: RecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit succession recertification required')
    existing = _recertification_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-three-succession-already-recertified', 'recertification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    validation = _validation_store.get(payload.monitoring_id)
    monitoring = _monitoring(payload.monitoring_id)
    if validation is None or monitoring is None:
        raise HTTPException(status_code=409, detail='Completed immutable remediation validation required')
    data = {'monitoring_id': payload.monitoring_id, 'validation_id': validation['validation_id'], 'continuity_monitor_id': monitoring['continuity_monitor_id'], 'corrected_hash': validation['corrected_hash'], 'recertification_reference': payload.recertification_reference, 'recertification_statement': payload.recertification_statement}
    record = {'recertification_id': str(uuid4()), **data, 'recertification_state': 'successor-next-generation-three-succession-recertified', 'integrity_hash': _hash(data), 'immutable': True, 'recertified_by': payload.actor, 'recertified_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _recertification_store[payload.monitoring_id] = record
    return {'state': 'telegram-successor-next-generation-three-succession-recertified', 'recertification': record, 'external_calls_made': 0}


@router.post('/baseline/renew')
def renew_baseline(payload: BaselineRenewalRequest) -> dict:
    if payload.renewal_phrase != _RENEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit assurance-baseline renewal required')
    existing = _baseline_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-renewed-successor-next-generation-three-baseline-already-active', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring(payload.monitoring_id)
    recertification = _recertification_store.get(payload.monitoring_id)
    validation = _validation_store.get(payload.monitoring_id)
    if monitoring is None or recertification is None or validation is None:
        raise HTTPException(status_code=409, detail='Completed validation and recertification required')
    previous_hash = monitoring['active_successor_next_generation_three_hash']
    if payload.renewed_successor_next_generation_three_hash == previous_hash:
        raise HTTPException(status_code=409, detail='Renewed baseline hash must differ from superseded hash')
    now = datetime.now(timezone.utc)
    data = {'monitoring_id': payload.monitoring_id, 'validation_id': validation['validation_id'], 'recertification_id': recertification['recertification_id'], 'superseded_hash': previous_hash, 'renewed_hash': payload.renewed_successor_next_generation_three_hash, 'baseline_reference': payload.baseline_reference, 'audit_interval_days': payload.audit_interval_days, 'validity_days': payload.validity_days}
    baseline = {'baseline_id': str(uuid4()), **data, 'baseline_state': 'renewed-successor-next-generation-three-baseline-active', 'next_audit_due_at': (now + timedelta(days=payload.audit_interval_days)).isoformat(), 'valid_until': (now + timedelta(days=payload.validity_days)).isoformat(), 'integrity_hash': _hash(data), 'immutable': True, 'renewed_by': payload.actor, 'renewed_at': now.isoformat(), 'external_calls_made': 0}
    _baseline_store[payload.monitoring_id] = baseline
    monitoring.update(monitoring_state='renewed-successor-next-generation-three-baseline-active', superseded_successor_next_generation_three_hash=previous_hash, active_successor_next_generation_three_hash=payload.renewed_successor_next_generation_three_hash, next_audit_due_at=baseline['next_audit_due_at'])
    continuity = _continuity(monitoring['continuity_monitor_id'])
    if continuity is not None:
        continuity.update(continuity_state='renewed-successor-next-generation-three-baseline-active', superseded_baseline_hash=previous_hash, active_baseline_hash=payload.renewed_successor_next_generation_three_hash, valid_until=baseline['valid_until'])
    succession = _succession_store.get(monitoring['continuity_monitor_id'])
    if succession is not None:
        succession.update(succession_state='successor-next-generation-three-baseline-superseded', superseded_by_baseline_id=baseline['baseline_id'])
    return {'state': 'telegram-renewed-successor-next-generation-three-baseline-established', 'baseline': baseline, 'monitoring': monitoring, 'continuity_monitor': continuity, 'external_calls_made': 0, 'next_layer': 'renewed-successor-next-generation-three-continuity-and-expiry-governance'}


@router.get('/status')
def status() -> dict:
    return {'remediation_validations': len(_validation_store), 'succession_recertifications': len(_recertification_store), 'renewed_baselines': len(_baseline_store), 'external_calls_made': 0, 'mode': 'successor-next-generation-three-remediation-validation-recertification-baseline-renewal'}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.381</title></head><body><h1>AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE RECERTIFICATION COMMAND CENTER</h1><p>Drift-remediation validation, succession recertification and renewed baseline governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
