from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_monitoring_v21_410 import (
    _drift_store,
    _monitoring_store,
    _resolution_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.411',
    tags=['auron-demo1-telegram-successor-next-generation-nine-recertification'],
)

_validation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_renewed_baseline_store: dict[str, dict] = {}

_VALIDATE_PHRASE = 'VALIDATE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE REMEDIATION'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE SUCCESSION'
_RENEW_BASELINE_PHRASE = 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE BASELINE'


class RemediationValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    resolution_id: str = Field(min_length=1, max_length=160)
    validation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_nine_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
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
    baseline_reference: str = Field(min_length=1, max_length=300)
    baseline_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_nine_recertification_store() -> None:
    _validation_store.clear()
    _recertification_store.clear()
    _renewed_baseline_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _resolution_by_id(resolution_id: str) -> dict | None:
    return next((item for item in _resolution_store.values() if item.get('resolution_id') == resolution_id), None)


def _validation_by_id(validation_id: str) -> dict | None:
    return next((item for item in _validation_store.values() if item.get('validation_id') == validation_id), None)


def _recertification_by_id(recertification_id: str) -> dict | None:
    return next((item for item in _recertification_store.values() if item.get('recertification_id') == recertification_id), None)


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


@router.post('/remediation/validate')
def validate_remediation(payload: RemediationValidationRequest) -> dict:
    if payload.validation_phrase != _VALIDATE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine remediation validation required')
    existing = _validation_store.get(payload.resolution_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-remediation-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    resolution = _resolution_by_id(payload.resolution_id)
    if resolution is None:
        raise HTTPException(status_code=404, detail='Resolved drift evidence not found')
    monitoring = _monitoring_by_id(resolution['monitoring_id'])
    corrected_hash = resolution['corrected_hash']
    checks = {
        'resolution_immutable': resolution.get('immutable') is True and bool(resolution.get('integrity_hash')),
        'monitoring_pending_validation': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-nine-drift-remediation-pending-validation',
        'observed_hash_matches': payload.observed_successor_next_generation_nine_hash == corrected_hash,
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Remediation validation blocked', 'blockers': blockers})
    data = {
        'resolution_id': resolution['resolution_id'],
        'monitoring_id': resolution['monitoring_id'],
        'validated_hash': corrected_hash,
        'validation_reference': payload.validation_reference,
        'validation_statement': payload.validation_statement,
        'checks': checks,
    }
    validation = {
        'validation_id': str(uuid4()),
        **data,
        'validation_state': 'successor-next-generation-nine-remediation-validated-stable',
        'integrity_hash': _hash(data),
        'immutable': True,
        'validated_by': payload.actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _validation_store[payload.resolution_id] = validation
    monitoring['monitoring_state'] = 'successor-next-generation-nine-recertification-pending'
    monitoring['validation_id'] = validation['validation_id']
    return {'state': 'telegram-successor-next-generation-nine-remediation-validated', 'validation': validation, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/succession/recertify')
def recertify_succession(payload: SuccessionRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine succession recertification required')
    existing = _recertification_store.get(payload.validation_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-succession-already-recertified', 'recertification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    validation = _validation_by_id(payload.validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail='Stable remediation validation not found')
    monitoring = _monitoring_by_id(validation['monitoring_id'])
    checks = {
        'validation_stable': validation.get('validation_state') == 'successor-next-generation-nine-remediation-validated-stable',
        'validation_immutable': validation.get('immutable') is True and bool(validation.get('integrity_hash')),
        'monitoring_pending_recertification': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-nine-recertification-pending',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Succession recertification blocked', 'blockers': blockers})
    data = {
        'validation_id': validation['validation_id'],
        'monitoring_id': validation['monitoring_id'],
        'active_successor_next_generation_nine_hash': validation['validated_hash'],
        'recertification_reference': payload.recertification_reference,
        'recertification_statement': payload.recertification_statement,
        'checks': checks,
    }
    recertification = {
        'recertification_id': str(uuid4()),
        **data,
        'recertification_state': 'successor-next-generation-nine-succession-recertified-stable',
        'integrity_hash': _hash(data),
        'immutable': True,
        'recertified_by': payload.actor,
        'recertified_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _recertification_store[payload.validation_id] = recertification
    monitoring['monitoring_state'] = 'successor-next-generation-nine-renewed-baseline-pending'
    monitoring['recertification_id'] = recertification['recertification_id']
    return {'state': 'telegram-successor-next-generation-nine-succession-recertified', 'recertification': recertification, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/baseline/renew')
def renew_baseline(payload: RenewedBaselineRequest) -> dict:
    if payload.renewal_phrase != _RENEW_BASELINE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine baseline renewal required')
    existing = _renewed_baseline_store.get(payload.recertification_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-baseline-already-renewed', 'baseline': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    recertification = _recertification_by_id(payload.recertification_id)
    if recertification is None:
        raise HTTPException(status_code=404, detail='Stable succession recertification not found')
    monitoring = _monitoring_by_id(recertification['monitoring_id'])
    checks = {
        'recertification_stable': recertification.get('recertification_state') == 'successor-next-generation-nine-succession-recertified-stable',
        'recertification_immutable': recertification.get('immutable') is True and bool(recertification.get('integrity_hash')),
        'monitoring_pending_baseline': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-nine-renewed-baseline-pending',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Renewed baseline blocked', 'blockers': blockers})
    data = {
        'recertification_id': recertification['recertification_id'],
        'monitoring_id': recertification['monitoring_id'],
        'active_successor_next_generation_nine_hash': recertification['active_successor_next_generation_nine_hash'],
        'baseline_reference': payload.baseline_reference,
        'baseline_statement': payload.baseline_statement,
        'checks': checks,
    }
    baseline = {
        'baseline_id': str(uuid4()),
        **data,
        'baseline_state': 'successor-next-generation-nine-renewed-baseline-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'renewed_by': payload.actor,
        'renewed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _renewed_baseline_store[payload.recertification_id] = baseline
    monitoring['monitoring_state'] = 'certified-successor-next-generation-nine-monitoring-active'
    monitoring['active_successor_next_generation_nine_hash'] = baseline['active_successor_next_generation_nine_hash']
    monitoring['renewed_baseline_id'] = baseline['baseline_id']
    monitoring.pop('failed_trigger_audit_id', None)
    monitoring.pop('drift_id', None)
    monitoring.pop('resolution_id', None)
    return {
        'state': 'telegram-successor-next-generation-nine-renewed-baseline-active',
        'baseline': baseline,
        'monitoring': monitoring,
        'external_calls_made': 0,
        'next_layer': 'successor-next-generation-nine-renewed-baseline-monitoring-and-expiry-governance',
    }


@router.get('/status')
def status() -> dict:
    return {
        'validations': len(_validation_store),
        'recertifications': len(_recertification_store),
        'renewed_baselines': len(_renewed_baseline_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-nine-remediation-validation-recertification-renewed-baseline-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.411</title></head><body><h1>AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE RECERTIFICATION COMMAND CENTER</h1><p>Drift remediation validation, succession recertification and renewed baseline governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
