from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_controlled_certificate_renewal_execution_v21_335 import (
    _handover_store,
    _renewal_execution_store,
)
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import (
    _baseline_metrics,
    _certificate_store,
)

router = APIRouter(prefix='/auron/demo1/v21.336', tags=['auron-demo1-telegram-post-renewal-continuity-governance'])

_continuity_store: dict[str, dict] = {}
_rollback_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM POST RENEWAL CONTINUITY OBSERVATION'
_COMPLETE_PHRASE = 'COMPLETE AURON TELEGRAM SUCCESSOR STABILIZATION'
_ROLLBACK_PHRASE = 'ROLL BACK AURON TELEGRAM CERTIFICATE HANDOVER'


class TelegramPostRenewalContinuityStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    renewal_execution_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=300)
    required_stable_observations: int = Field(default=3, ge=1, le=100)
    minimum_reliability_score: float = Field(default=85.0, ge=0.0, le=100.0)
    maximum_reliability_drop: float = Field(default=5.0, ge=0.0, le=100.0)


class TelegramPostRenewalContinuityObserveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)


class TelegramSuccessorStabilizationCompleteRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    completion_phrase: str = Field(min_length=1, max_length=300)


class TelegramCertificateRollbackRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    rollback_phrase: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=1200)


def reset_telegram_post_renewal_continuity_governance_store() -> None:
    _continuity_store.clear()
    _rollback_store.clear()


def _execution_by_id(execution_id: str) -> dict | None:
    return next((item for item in _renewal_execution_store.values() if item.get('renewal_execution_id') == execution_id), None)


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/start')
def start_post_renewal_continuity(payload: TelegramPostRenewalContinuityStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit post-renewal continuity observation approval required')
    existing = _continuity_store.get(payload.renewal_execution_id)
    if existing is not None:
        return {'state': 'telegram-post-renewal-continuity-already-started', 'continuity': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    execution = _execution_by_id(payload.renewal_execution_id)
    handover = _handover_store.get(payload.renewal_execution_id)
    if execution is None or handover is None:
        raise HTTPException(status_code=409, detail='Completed v21.335 zero-downtime handover required')
    if execution.get('execution_state') != 'completed-zero-downtime-handover' or handover.get('handover_state') != 'committed-zero-downtime':
        raise HTTPException(status_code=409, detail='Renewal execution and handover are not completed')
    source = _certificate_by_id(execution['source_certificate_id'])
    successor = _certificate_by_id(execution['successor_certificate_id'])
    if source is None or successor is None:
        raise HTTPException(status_code=409, detail='Source or successor certificate missing')
    chat_id = execution['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    checks = {
        'source_superseded': source.get('certificate_state') == 'superseded-after-governed-renewal',
        'successor_certified': successor.get('certificate_state') == 'certified',
        'successor_is_active_certificate': bool(go_live and go_live.get('service_certificate_id') == successor['certificate_id']),
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Post-renewal continuity observation blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'continuity_id': str(uuid4()),
        'renewal_execution_id': payload.renewal_execution_id,
        'handover_id': handover['handover_id'],
        'telegram_chat_id': chat_id,
        'source_certificate_id': source['certificate_id'],
        'successor_certificate_id': successor['certificate_id'],
        'required_stable_observations': payload.required_stable_observations,
        'minimum_reliability_score': payload.minimum_reliability_score,
        'maximum_reliability_drop': payload.maximum_reliability_drop,
        'successor_baseline_score': successor['runtime_reliability_score'],
        'stable_observations': 0,
        'degraded_observations': 0,
        'observation_history': [],
        'continuity_state': 'active-successor-stabilization-window',
        'checks': checks,
        'started_by': payload.actor,
        'started_at': now,
        'completed_at': None,
        'external_calls_made': 0,
    }
    _continuity_store[payload.renewal_execution_id] = record
    return {'state': 'telegram-post-renewal-continuity-started', 'continuity': record, 'external_calls_made': 0}


@router.post('/observe')
def observe_post_renewal_continuity(payload: TelegramPostRenewalContinuityObserveRequest) -> dict:
    record = _continuity_by_id(payload.continuity_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-renewal continuity record not found')
    if record.get('continuity_state') != 'active-successor-stabilization-window':
        return {'state': 'telegram-post-renewal-continuity-already-terminal', 'continuity': record, 'idempotent_replay': True, 'external_calls_made': 0}
    successor = _certificate_by_id(record['successor_certificate_id'])
    source = _certificate_by_id(record['source_certificate_id'])
    if successor is None or source is None:
        raise HTTPException(status_code=409, detail='Source or successor certificate missing')
    chat_id = record['telegram_chat_id']
    metrics = _baseline_metrics(chat_id)
    go_live = _go_live_store.get(chat_id)
    score_drop = round(record['successor_baseline_score'] - metrics['runtime_reliability_score'], 2)
    checks = {
        'successor_certified': successor.get('certificate_state') == 'certified',
        'source_preserved_for_rollback': source.get('certificate_state') == 'superseded-after-governed-renewal',
        'successor_is_active_certificate': bool(go_live and go_live.get('service_certificate_id') == successor['certificate_id']),
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
        'minimum_reliability_met': metrics['runtime_reliability_score'] >= record['minimum_reliability_score'],
        'reliability_drop_within_limit': score_drop <= record['maximum_reliability_drop'],
    }
    stable = all(checks.values())
    now = datetime.now(timezone.utc).isoformat()
    observation = {
        'observation_id': str(uuid4()),
        'metrics': metrics,
        'score_drop': score_drop,
        'checks': checks,
        'stable': stable,
        'observed_by': payload.actor,
        'observed_at': now,
    }
    record['observation_history'].append(observation)
    if stable:
        record['stable_observations'] += 1
        state = 'telegram-successor-stable-observation-recorded'
    else:
        record['degraded_observations'] += 1
        record['continuity_state'] = 'automatic-rollback-required'
        record['rollback_blockers'] = [name for name, passed in checks.items() if not passed]
        state = 'telegram-successor-degraded-automatic-rollback-required'
    return {'state': state, 'continuity': record, 'observation': observation, 'external_calls_made': 0}


@router.post('/complete')
def complete_successor_stabilization(payload: TelegramSuccessorStabilizationCompleteRequest) -> dict:
    if payload.completion_phrase != _COMPLETE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor stabilization completion approval required')
    record = _continuity_by_id(payload.continuity_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-renewal continuity record not found')
    if record.get('continuity_state') == 'completed-stable-successor':
        return {'state': 'telegram-successor-stabilization-already-completed', 'continuity': record, 'idempotent_replay': True, 'external_calls_made': 0}
    checks = {
        'stabilization_window_active': record.get('continuity_state') == 'active-successor-stabilization-window',
        'stable_observation_threshold_met': record['stable_observations'] >= record['required_stable_observations'],
        'no_degraded_observations': record['degraded_observations'] == 0,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor stabilization completion blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    evidence_payload = {
        'continuity_id': record['continuity_id'],
        'renewal_execution_id': record['renewal_execution_id'],
        'successor_certificate_id': record['successor_certificate_id'],
        'stable_observations': record['stable_observations'],
        'checks': checks,
    }
    record.update(
        continuity_state='completed-stable-successor',
        stabilization_integrity_hash=_hash(evidence_payload),
        stabilization_evidence_immutable=True,
        completed_by=payload.actor,
        completed_at=now,
    )
    return {'state': 'telegram-successor-stabilization-completed', 'continuity': record, 'external_calls_made': 0, 'next_layer': 'certificate-retirement-governance'}


@router.post('/rollback')
def rollback_certificate_handover(payload: TelegramCertificateRollbackRequest) -> dict:
    if payload.rollback_phrase != _ROLLBACK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate rollback approval required')
    record = _continuity_by_id(payload.continuity_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-renewal continuity record not found')
    existing = _rollback_store.get(record['continuity_id'])
    if existing is not None:
        return {'state': 'telegram-certificate-rollback-already-committed', 'rollback': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    if record.get('continuity_state') != 'automatic-rollback-required':
        raise HTTPException(status_code=409, detail='Rollback is allowed only after degraded successor continuity')
    source = _certificate_by_id(record['source_certificate_id'])
    successor = _certificate_by_id(record['successor_certificate_id'])
    if source is None or successor is None:
        raise HTTPException(status_code=409, detail='Source or successor certificate missing')
    chat_id = record['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    checks = {
        'source_available': source.get('certificate_state') == 'superseded-after-governed-renewal',
        'source_integrity_present': bool(source.get('integrity_hash')) and source.get('immutable') is True,
        'successor_is_active_certificate': bool(go_live and go_live.get('service_certificate_id') == successor['certificate_id']),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certificate rollback blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    rollback_payload = {
        'continuity_id': record['continuity_id'],
        'source_certificate_id': source['certificate_id'],
        'successor_certificate_id': successor['certificate_id'],
        'reason': payload.reason,
        'checks': checks,
    }
    rollback = {
        'rollback_id': str(uuid4()),
        **rollback_payload,
        'rollback_state': 'committed-source-restored',
        'integrity_hash': _hash(rollback_payload),
        'immutable': True,
        'committed_by': payload.actor,
        'committed_at': now,
        'external_calls_made': 0,
    }
    source.update(certificate_state='certified', restored_at=now, restored_by=payload.actor)
    successor.update(certificate_state='rolled-back-after-continuity-degradation', rolled_back_at=now)
    if go_live is not None:
        go_live.update(service_certificate_id=source['certificate_id'], go_live_state='rollback-restored-certified-service', continuous_mode_active=True)
    _circuit_store.setdefault(chat_id, {'telegram_chat_id': chat_id}).update(state='closed', reset_at=now, reset_by=payload.actor)
    record.update(continuity_state='rolled-back-source-restored', rolled_back_at=now, rollback_id=rollback['rollback_id'])
    _rollback_store[record['continuity_id']] = rollback
    return {'state': 'telegram-certificate-rollback-committed', 'rollback': rollback, 'active_certificate': source, 'external_calls_made': 0}


@router.get('/status')
def post_renewal_continuity_status() -> dict:
    items = list(_continuity_store.values())
    return {
        'continuity_records': len(items),
        'active_stabilization_windows': sum(1 for item in items if item.get('continuity_state') == 'active-successor-stabilization-window'),
        'rollback_required': sum(1 for item in items if item.get('continuity_state') == 'automatic-rollback-required'),
        'stable_successors': sum(1 for item in items if item.get('continuity_state') == 'completed-stable-successor'),
        'rollbacks_committed': len(_rollback_store),
        'external_calls_made': 0,
        'mode': 'post-renewal-continuity-successor-stabilization-automatic-rollback-governance',
    }


@router.get('/continuity')
def list_continuity_records() -> dict:
    return {'count': len(_continuity_store), 'items': list(_continuity_store.values()), 'external_calls_made': 0}


@router.get('/rollbacks')
def list_rollbacks() -> dict:
    return {'count': len(_rollback_store), 'items': list(_rollback_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_controlled_certificate_renewal_execution_v21_335 import command_center as v21_335_command_center
    return v21_335_command_center().replace('v21.335', 'v21.336').replace(
        'AURON TELEGRAM CONTROLLED CERTIFICATE RENEWAL EXECUTION COMMAND CENTER',
        'AURON TELEGRAM POST RENEWAL CONTINUITY GOVERNANCE COMMAND CENTER',
    )
