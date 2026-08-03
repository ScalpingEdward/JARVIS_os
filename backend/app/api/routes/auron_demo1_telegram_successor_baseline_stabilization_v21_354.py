from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_expired_baseline_restoration_v21_353 import (
    _restoration_store,
    _successor_store,
)
from app.api.routes.auron_demo1_telegram_renewed_assurance_continuity_v21_352 import (
    _continuity_store,
)

router = APIRouter(prefix='/auron/demo1/v21.354', tags=['auron-demo1-telegram-successor-baseline-stabilization'])

_stabilization_store: dict[str, dict] = {}
_observation_store: dict[str, list[dict]] = {}
_certification_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM SUCCESSOR BASELINE STABILIZATION'
_OBSERVE_PHRASE = 'OBSERVE AURON TELEGRAM RESTORED CONTINUITY'
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM SUCCESSOR BASELINE SUCCESSION'


class SuccessorBaselineStabilizationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    stabilization_hours: int = Field(default=168, ge=1, le=8760)
    minimum_observations: int = Field(default=3, ge=1, le=100)


class RestoredContinuityObservationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    observation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    observation_statement: str = Field(min_length=1, max_length=1800)
    observed_at: datetime | None = None


class SuccessionCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    certification_reference: str = Field(min_length=1, max_length=300)
    certification_statement: str = Field(min_length=1, max_length=1800)
    certified_at: datetime | None = None


def reset_telegram_successor_baseline_stabilization_store() -> None:
    _stabilization_store.clear()
    _observation_store.clear()
    _certification_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _continuity_by_id(continuity_id: str) -> dict | None:
    return next((item for item in _continuity_store.values() if item.get('continuity_id') == continuity_id), None)


def _stabilization_by_id(stabilization_id: str) -> dict | None:
    return next((item for item in _stabilization_store.values() if item.get('stabilization_id') == stabilization_id), None)


@router.post('/stabilization/start')
def start_successor_baseline_stabilization(payload: SuccessorBaselineStabilizationStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-baseline stabilization approval required')
    existing = _stabilization_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-successor-baseline-stabilization-already-started', 'stabilization': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    successor = _successor_store.get(payload.continuity_id)
    restoration = _restoration_store.get(payload.continuity_id)
    if continuity is None or successor is None or restoration is None:
        raise HTTPException(status_code=409, detail='Completed v21.353 restoration and successor baseline required')
    checks = {
        'successor_active': successor.get('successor_state') == 'successor-assurance-baseline-active',
        'successor_immutable': successor.get('immutable') is True and bool(successor.get('integrity_hash')),
        'restoration_complete': restoration.get('restoration_state') == 'assurance-continuity-restored-awaiting-successor-baseline',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'continuity_active': continuity.get('continuity_state') == 'renewed-assurance-continuity-active',
        'successor_hash_active': successor.get('successor_baseline_hash') == continuity.get('active_baseline_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-baseline stabilization blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'continuity_id': continuity['continuity_id'],
        'successor_id': successor['successor_id'],
        'restoration_id': restoration['restoration_id'],
        'successor_baseline_hash': successor['successor_baseline_hash'],
        'stabilization_hours': payload.stabilization_hours,
        'minimum_observations': payload.minimum_observations,
        'stabilization_ends_at': (now + timedelta(hours=payload.stabilization_hours)).isoformat(),
        'checks': checks,
    }
    stabilization = {
        'stabilization_id': str(uuid4()),
        **data,
        'stabilization_state': 'successor-baseline-stabilization-active',
        'integrity_hash': _hash(data),
        'observation_count': 0,
        'healthy_observation_count': 0,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _stabilization_store[payload.continuity_id] = stabilization
    continuity['continuity_state'] = 'successor-baseline-stabilization-active'
    return {'state': 'telegram-successor-baseline-stabilization-started', 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/continuity/observe')
def observe_restored_continuity(payload: RestoredContinuityObservationRequest) -> dict:
    if payload.observation_phrase != _OBSERVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit restored-continuity observation approval required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Successor-baseline stabilization not found')
    if stabilization.get('stabilization_state') not in {'successor-baseline-stabilization-active', 'successor-baseline-observation-complete'}:
        raise HTTPException(status_code=409, detail='Successor-baseline stabilization is not open for observation')
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    observations = _observation_store.setdefault(stabilization['stabilization_id'], [])
    sequence = len(observations) + 1
    hash_matches = payload.observed_successor_hash == stabilization['successor_baseline_hash']
    healthy = hash_matches and payload.continuity_state == 'healthy'
    data = {
        'stabilization_id': stabilization['stabilization_id'],
        'continuity_id': stabilization['continuity_id'],
        'sequence': sequence,
        'expected_successor_hash': stabilization['successor_baseline_hash'],
        'observed_successor_hash': payload.observed_successor_hash,
        'hash_matches': hash_matches,
        'continuity_state': payload.continuity_state,
        'healthy': healthy,
        'observation_statement': payload.observation_statement,
    }
    observation = {
        'observation_id': str(uuid4()),
        **data,
        'observation_state': 'restored-continuity-healthy' if healthy else 'successor-baseline-instability-detected',
        'integrity_hash': _hash(data),
        'immutable': True,
        'observed_by': payload.actor,
        'observed_at': observed_at.isoformat(),
        'external_calls_made': 0,
    }
    observations.append(observation)
    healthy_count = sum(1 for item in observations if item.get('healthy') is True)
    stabilization.update(
        observation_count=len(observations),
        healthy_observation_count=healthy_count,
        last_observation_id=observation['observation_id'],
    )
    continuity = _continuity_by_id(stabilization['continuity_id'])
    if not healthy:
        stabilization['stabilization_state'] = 'successor-baseline-stabilization-failed-restoration-required'
        if continuity is not None:
            continuity['continuity_state'] = 'successor-baseline-instability-remediation-required'
    elif healthy_count >= stabilization['minimum_observations']:
        stabilization['stabilization_state'] = 'successor-baseline-observation-complete'
    return {'state': f"telegram-{observation['observation_state']}", 'observation': observation, 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/succession/certify')
def certify_successor_baseline_succession(payload: SuccessionCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-baseline succession certification required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Successor-baseline stabilization not found')
    existing = _certification_store.get(stabilization['stabilization_id'])
    if existing is not None:
        return {'state': 'telegram-successor-baseline-succession-already-certified', 'certification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certified_at = payload.certified_at or datetime.now(timezone.utc)
    observations = _observation_store.get(stabilization['stabilization_id'], [])
    checks = {
        'observation_complete': stabilization.get('stabilization_state') == 'successor-baseline-observation-complete',
        'stabilization_window_elapsed': certified_at >= datetime.fromisoformat(stabilization['stabilization_ends_at']),
        'minimum_observations_met': stabilization.get('healthy_observation_count', 0) >= stabilization['minimum_observations'],
        'all_observations_healthy': bool(observations) and all(item.get('healthy') is True for item in observations),
        'successor_hash_consistent': all(item.get('observed_successor_hash') == stabilization['successor_baseline_hash'] for item in observations),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-baseline succession certification blocked', 'blockers': blockers})
    data = {
        'stabilization_id': stabilization['stabilization_id'],
        'continuity_id': stabilization['continuity_id'],
        'successor_id': stabilization['successor_id'],
        'successor_baseline_hash': stabilization['successor_baseline_hash'],
        'observation_count': len(observations),
        'certification_reference': payload.certification_reference,
        'certification_statement': payload.certification_statement,
        'checks': checks,
    }
    certification = {
        'certification_id': str(uuid4()),
        **data,
        'certification_state': 'successor-baseline-succession-certified-stable',
        'integrity_hash': _hash(data),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': certified_at.isoformat(),
        'external_calls_made': 0,
    }
    _certification_store[stabilization['stabilization_id']] = certification
    stabilization['stabilization_state'] = 'successor-baseline-stabilization-certified-closed'
    continuity = _continuity_by_id(stabilization['continuity_id'])
    if continuity is not None:
        continuity.update(
            continuity_state='renewed-assurance-continuity-active',
            last_succession_certification_id=certification['certification_id'],
        )
    successor = _successor_store.get(stabilization['continuity_id'])
    if successor is not None:
        successor.update(
            successor_state='successor-assurance-baseline-certified-stable',
            succession_certification_id=certification['certification_id'],
        )
    return {'state': 'telegram-successor-baseline-succession-certified', 'certification': certification, 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'certified-successor-baseline-long-term-monitoring-governance'}


@router.get('/status')
def successor_baseline_stabilization_status() -> dict:
    return {
        'stabilizations': len(_stabilization_store),
        'continuity_observations': sum(len(items) for items in _observation_store.values()),
        'succession_certifications': len(_certification_store),
        'failed_stabilizations': sum(1 for item in _stabilization_store.values() if item.get('stabilization_state') == 'successor-baseline-stabilization-failed-restoration-required'),
        'external_calls_made': 0,
        'mode': 'successor-baseline-stabilization-restored-continuity-observation-succession-certification',
    }


@router.get('/stabilizations')
def list_stabilizations() -> dict:
    return {'count': len(_stabilization_store), 'items': list(_stabilization_store.values()), 'external_calls_made': 0}


@router.get('/observations')
def list_observations() -> dict:
    items = [item for observations in _observation_store.values() for item in observations]
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/certifications')
def list_certifications() -> dict:
    return {'count': len(_certification_store), 'items': list(_certification_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_expired_baseline_restoration_v21_353 import command_center as v21_353_command_center
    return v21_353_command_center().replace('v21.353', 'v21.354').replace(
        'AURON TELEGRAM EXPIRED BASELINE RESTORATION COMMAND CENTER',
        'AURON TELEGRAM SUCCESSOR BASELINE STABILIZATION COMMAND CENTER',
    )
