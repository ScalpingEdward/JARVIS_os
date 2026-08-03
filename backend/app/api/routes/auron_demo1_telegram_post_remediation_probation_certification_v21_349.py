from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_closed_record_remediation_reclosure_v21_348 import (
    _reclosure_store,
    _remediation_store,
    _supersession_store,
)
from app.api.routes.auron_demo1_telegram_closed_record_integrity_v21_347 import _record_store

router = APIRouter(prefix='/auron/demo1/v21.349', tags=['auron-demo1-telegram-post-remediation-probation-certification'])

_probation_store: dict[str, dict] = {}
_observation_store: dict[str, list[dict]] = {}
_certification_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM POST REMEDIATION PROBATION'
_OBSERVE_PHRASE = 'OBSERVE AURON TELEGRAM CORRECTIVE EVIDENCE'
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM GOVERNED RECLOSURE'


class PostRemediationProbationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    probation_hours: int = Field(default=168, ge=1, le=8760)
    minimum_observations: int = Field(default=3, ge=1, le=100)


class CorrectiveEvidenceObservationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    probation_id: str = Field(min_length=1, max_length=160)
    observation_phrase: str = Field(min_length=1, max_length=320)
    observed_evidence_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    observation_statement: str = Field(min_length=1, max_length=1800)
    observed_at: datetime | None = None


class ReclosureCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    probation_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    certification_reference: str = Field(min_length=1, max_length=300)
    certification_statement: str = Field(min_length=1, max_length=1800)
    certified_at: datetime | None = None


def reset_telegram_post_remediation_probation_certification_store() -> None:
    _probation_store.clear()
    _observation_store.clear()
    _certification_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _record_by_id(record_id: str) -> dict | None:
    return next((item for item in _record_store.values() if item.get('record_id') == record_id), None)


def _probation_by_id(probation_id: str) -> dict | None:
    return next((item for item in _probation_store.values() if item.get('probation_id') == probation_id), None)


@router.post('/probation/start')
def start_post_remediation_probation(payload: PostRemediationProbationStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit post-remediation probation approval required')
    existing = _probation_store.get(payload.record_id)
    if existing is not None:
        return {'state': 'telegram-post-remediation-probation-already-started', 'probation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    record = _record_by_id(payload.record_id)
    reclosure = _reclosure_store.get(payload.record_id)
    remediation = _remediation_store.get(payload.record_id)
    supersession = _supersession_store.get(payload.record_id)
    if record is None or reclosure is None or remediation is None or supersession is None:
        raise HTTPException(status_code=409, detail='Completed v21.348 remediation and reclosure evidence required')
    checks = {
        'reclosure_completed': reclosure.get('reclosure_state') == 'governed-disclosure-lifecycle-reclosed',
        'reclosure_immutable': reclosure.get('immutable') is True and bool(reclosure.get('integrity_hash')),
        'remediation_completed': remediation.get('remediation_state') == 'remediation-completed-reclosed',
        'supersession_immutable': supersession.get('immutable') is True and bool(supersession.get('integrity_hash')),
        'corrected_hash_active': supersession.get('corrected_evidence_hash') == record.get('baseline_evidence_hash'),
        'record_reclosed': record.get('record_state') == 'retained-closed-disclosure-record',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Post-remediation probation blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'reclosure_id': reclosure['reclosure_id'],
        'supersession_id': supersession['supersession_id'],
        'corrected_evidence_hash': supersession['corrected_evidence_hash'],
        'probation_hours': payload.probation_hours,
        'minimum_observations': payload.minimum_observations,
        'probation_ends_at': (now + timedelta(hours=payload.probation_hours)).isoformat(),
        'checks': checks,
    }
    probation = {
        'probation_id': str(uuid4()),
        **data,
        'probation_state': 'post-remediation-probation-active',
        'baseline_hash': _hash(data),
        'observation_count': 0,
        'healthy_observation_count': 0,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _probation_store[payload.record_id] = probation
    record['record_state'] = 'post-remediation-probation-active'
    return {'state': 'telegram-post-remediation-probation-started', 'probation': probation, 'record': record, 'external_calls_made': 0}


@router.post('/evidence/observe')
def observe_corrective_evidence(payload: CorrectiveEvidenceObservationRequest) -> dict:
    if payload.observation_phrase != _OBSERVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit corrective-evidence observation approval required')
    probation = _probation_by_id(payload.probation_id)
    if probation is None:
        raise HTTPException(status_code=404, detail='Telegram post-remediation probation not found')
    if probation.get('probation_state') not in {'post-remediation-probation-active', 'post-remediation-probation-observation-complete'}:
        raise HTTPException(status_code=409, detail='Post-remediation probation is not open for observation')
    observations = _observation_store.setdefault(probation['probation_id'], [])
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    sequence = len(observations) + 1
    hash_matches = payload.observed_evidence_hash == probation['corrected_evidence_hash']
    healthy = hash_matches and payload.control_state == 'healthy'
    data = {
        'probation_id': probation['probation_id'],
        'record_id': probation['record_id'],
        'sequence': sequence,
        'observed_evidence_hash': payload.observed_evidence_hash,
        'expected_evidence_hash': probation['corrected_evidence_hash'],
        'hash_matches': hash_matches,
        'control_state': payload.control_state,
        'healthy': healthy,
        'observation_statement': payload.observation_statement,
    }
    observation = {
        'observation_id': str(uuid4()),
        **data,
        'observation_state': 'corrective-evidence-healthy' if healthy else 'corrective-evidence-drift-detected',
        'integrity_hash': _hash(data),
        'immutable': True,
        'observed_by': payload.actor,
        'observed_at': observed_at.isoformat(),
        'external_calls_made': 0,
    }
    observations.append(observation)
    healthy_count = sum(1 for item in observations if item.get('healthy'))
    probation.update(observation_count=len(observations), healthy_observation_count=healthy_count, last_observation_id=observation['observation_id'])
    if not healthy:
        probation['probation_state'] = 'post-remediation-probation-failed-remediation-required'
    elif healthy_count >= probation['minimum_observations']:
        probation['probation_state'] = 'post-remediation-probation-observation-complete'
    return {'state': f"telegram-{observation['observation_state']}", 'observation': observation, 'probation': probation, 'external_calls_made': 0}


@router.post('/reclosure/certify')
def certify_governed_reclosure(payload: ReclosureCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit governed reclosure certification approval required')
    probation = _probation_by_id(payload.probation_id)
    if probation is None:
        raise HTTPException(status_code=404, detail='Telegram post-remediation probation not found')
    existing = _certification_store.get(probation['probation_id'])
    if existing is not None:
        return {'state': 'telegram-governed-reclosure-already-certified', 'certification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certified_at = payload.certified_at or datetime.now(timezone.utc)
    observations = _observation_store.get(probation['probation_id'], [])
    checks = {
        'probation_observation_complete': probation.get('probation_state') == 'post-remediation-probation-observation-complete',
        'probation_window_elapsed': certified_at >= datetime.fromisoformat(probation['probation_ends_at']),
        'minimum_observations_met': probation.get('healthy_observation_count', 0) >= probation['minimum_observations'],
        'all_observations_healthy': bool(observations) and all(item.get('healthy') is True for item in observations),
        'corrected_hash_consistent': all(item.get('observed_evidence_hash') == probation['corrected_evidence_hash'] for item in observations),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Governed reclosure certification blocked', 'blockers': blockers})
    data = {
        'probation_id': probation['probation_id'],
        'record_id': probation['record_id'],
        'reclosure_id': probation['reclosure_id'],
        'corrected_evidence_hash': probation['corrected_evidence_hash'],
        'observation_count': len(observations),
        'certification_reference': payload.certification_reference,
        'certification_statement': payload.certification_statement,
        'checks': checks,
    }
    certification = {
        'certification_id': str(uuid4()),
        **data,
        'certification_state': 'governed-reclosure-certified-stable',
        'integrity_hash': _hash(data),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': certified_at.isoformat(),
        'external_calls_made': 0,
    }
    _certification_store[probation['probation_id']] = certification
    probation['probation_state'] = 'post-remediation-probation-certified-closed'
    record = _record_by_id(probation['record_id'])
    if record is not None:
        record.update(record_state='retained-closed-disclosure-record', last_reclosure_certification_id=certification['certification_id'])
    return {'state': 'telegram-governed-reclosure-certified', 'certification': certification, 'probation': probation, 'record': record, 'external_calls_made': 0, 'next_layer': 'certified-reclosure-long-term-assurance-governance'}


@router.get('/status')
def post_remediation_probation_status() -> dict:
    return {
        'probations': len(_probation_store),
        'observations': sum(len(items) for items in _observation_store.values()),
        'certifications': len(_certification_store),
        'failed_probations': sum(1 for item in _probation_store.values() if item.get('probation_state') == 'post-remediation-probation-failed-remediation-required'),
        'external_calls_made': 0,
        'mode': 'post-remediation-probation-corrective-evidence-observation-reclosure-certification',
    }


@router.get('/probations')
def list_probations() -> dict:
    return {'count': len(_probation_store), 'items': list(_probation_store.values()), 'external_calls_made': 0}


@router.get('/observations')
def list_observations() -> dict:
    items = [item for observations in _observation_store.values() for item in observations]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/certifications')
def list_certifications() -> dict:
    return {'count': len(_certification_store), 'items': list(_certification_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_closed_record_remediation_reclosure_v21_348 import command_center as v21_348_command_center
    return v21_348_command_center().replace('v21.348', 'v21.349').replace(
        'AURON TELEGRAM CLOSED RECORD REMEDIATION RECLOSURE COMMAND CENTER',
        'AURON TELEGRAM POST REMEDIATION PROBATION CERTIFICATION COMMAND CENTER',
    )
