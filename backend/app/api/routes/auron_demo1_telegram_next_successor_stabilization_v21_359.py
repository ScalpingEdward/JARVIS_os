from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_restoration_v21_358 import (
    _restoration_store,
    _succession_store,
)
from app.api.routes.auron_demo1_telegram_renewed_successor_continuity_v21_357 import _continuity_store

router = APIRouter(prefix='/auron/demo1/v21.359', tags=['auron-demo1-telegram-next-successor-stabilization'])
_stabilization_store: dict[str, dict] = {}
_observation_store: dict[str, list[dict]] = {}
_certification_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM NEXT SUCCESSOR STABILIZATION'
_OBSERVE_PHRASE = 'OBSERVE AURON TELEGRAM NEXT SUCCESSOR CONTINUITY'
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM NEXT SUCCESSOR SUCCESSION'


class StabilizationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    continuity_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    stabilization_hours: int = Field(default=168, ge=1, le=8760)
    minimum_observations: int = Field(default=3, ge=1, le=100)


class ContinuityObservationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    observation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    continuity_state: str = Field(pattern='^(healthy|degraded|failed)$')
    statement: str = Field(min_length=1, max_length=1800)
    observed_at: datetime | None = None


class SuccessionCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    certification_reference: str = Field(min_length=1, max_length=300)
    certification_statement: str = Field(min_length=1, max_length=1800)
    certified_at: datetime | None = None


def reset_telegram_next_successor_stabilization_store() -> None:
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
def start_stabilization(payload: StabilizationStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit next-successor stabilization approval required')
    existing = _stabilization_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-next-successor-stabilization-already-started', 'stabilization': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    succession = _succession_store.get(payload.continuity_id)
    restoration = _restoration_store.get(payload.continuity_id)
    if continuity is None or succession is None or restoration is None:
        raise HTTPException(status_code=409, detail='Completed v21.358 restoration and next-successor baseline required')
    checks = {
        'succession_active': succession.get('succession_state') == 'next-successor-baseline-active',
        'succession_immutable': succession.get('immutable') is True and bool(succession.get('integrity_hash')),
        'restoration_complete': restoration.get('restoration_state') == 'renewed-successor-continuity-restored-awaiting-next-successor',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'continuity_active': continuity.get('continuity_state') == 'renewed-successor-continuity-active',
        'successor_hash_active': succession.get('next_successor_hash') == continuity.get('active_baseline_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Next-successor stabilization blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'continuity_id': continuity['continuity_id'],
        'succession_id': succession['succession_id'],
        'restoration_id': restoration['restoration_id'],
        'next_successor_hash': succession['next_successor_hash'],
        'stabilization_hours': payload.stabilization_hours,
        'minimum_observations': payload.minimum_observations,
        'stabilization_ends_at': (now + timedelta(hours=payload.stabilization_hours)).isoformat(),
        'checks': checks,
    }
    stabilization = {
        'stabilization_id': str(uuid4()),
        **data,
        'stabilization_state': 'next-successor-stabilization-active',
        'observation_count': 0,
        'healthy_observation_count': 0,
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _stabilization_store[payload.continuity_id] = stabilization
    continuity['continuity_state'] = 'next-successor-stabilization-active'
    return {'state': 'telegram-next-successor-stabilization-started', 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/continuity/observe')
def observe_continuity(payload: ContinuityObservationRequest) -> dict:
    if payload.observation_phrase != _OBSERVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit next-successor continuity observation required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Next-successor stabilization not found')
    if stabilization.get('stabilization_state') not in {'next-successor-stabilization-active', 'next-successor-observation-complete'}:
        raise HTTPException(status_code=409, detail='Next-successor stabilization is not open for observation')
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    observations = _observation_store.setdefault(stabilization['stabilization_id'], [])
    sequence = len(observations) + 1
    hash_matches = payload.observed_successor_hash == stabilization['next_successor_hash']
    healthy = hash_matches and payload.continuity_state == 'healthy'
    data = {
        'stabilization_id': stabilization['stabilization_id'],
        'continuity_id': stabilization['continuity_id'],
        'sequence': sequence,
        'expected_successor_hash': stabilization['next_successor_hash'],
        'observed_successor_hash': payload.observed_successor_hash,
        'hash_matches': hash_matches,
        'continuity_state': payload.continuity_state,
        'healthy': healthy,
        'statement': payload.statement,
    }
    observation = {
        'observation_id': str(uuid4()),
        **data,
        'observation_state': 'next-successor-continuity-healthy' if healthy else 'next-successor-instability-detected',
        'integrity_hash': _hash(data),
        'immutable': True,
        'observed_by': payload.actor,
        'observed_at': observed_at.isoformat(),
        'external_calls_made': 0,
    }
    observations.append(observation)
    healthy_count = sum(1 for item in observations if item.get('healthy') is True)
    stabilization.update(observation_count=len(observations), healthy_observation_count=healthy_count, last_observation_id=observation['observation_id'])
    continuity = _continuity_by_id(stabilization['continuity_id'])
    if not healthy:
        stabilization['stabilization_state'] = 'next-successor-stabilization-failed-remediation-required'
        if continuity is not None:
            continuity['continuity_state'] = 'next-successor-instability-remediation-required'
    elif healthy_count >= stabilization['minimum_observations']:
        stabilization['stabilization_state'] = 'next-successor-observation-complete'
    return {'state': f"telegram-{observation['observation_state']}", 'observation': observation, 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/succession/certify')
def certify_succession(payload: SuccessionCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit next-successor succession certification required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Next-successor stabilization not found')
    existing = _certification_store.get(stabilization['stabilization_id'])
    if existing is not None:
        return {'state': 'telegram-next-successor-succession-already-certified', 'certification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certified_at = payload.certified_at or datetime.now(timezone.utc)
    observations = _observation_store.get(stabilization['stabilization_id'], [])
    checks = {
        'observation_complete': stabilization.get('stabilization_state') == 'next-successor-observation-complete',
        'stabilization_window_elapsed': certified_at >= datetime.fromisoformat(stabilization['stabilization_ends_at']),
        'minimum_observations_met': stabilization.get('healthy_observation_count', 0) >= stabilization['minimum_observations'],
        'all_observations_healthy': bool(observations) and all(item.get('healthy') is True for item in observations),
        'successor_hash_consistent': all(item.get('observed_successor_hash') == stabilization['next_successor_hash'] for item in observations),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Next-successor succession certification blocked', 'blockers': blockers})
    data = {
        'stabilization_id': stabilization['stabilization_id'],
        'continuity_id': stabilization['continuity_id'],
        'succession_id': stabilization['succession_id'],
        'next_successor_hash': stabilization['next_successor_hash'],
        'observation_count': len(observations),
        'certification_reference': payload.certification_reference,
        'certification_statement': payload.certification_statement,
        'checks': checks,
    }
    certification = {
        'certification_id': str(uuid4()),
        **data,
        'certification_state': 'next-successor-succession-certified-stable',
        'integrity_hash': _hash(data),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': certified_at.isoformat(),
        'external_calls_made': 0,
    }
    _certification_store[stabilization['stabilization_id']] = certification
    stabilization['stabilization_state'] = 'next-successor-stabilization-certified-closed'
    continuity = _continuity_by_id(stabilization['continuity_id'])
    if continuity is not None:
        continuity.update(continuity_state='renewed-successor-continuity-active', last_next_successor_certification_id=certification['certification_id'])
    succession = _succession_store.get(stabilization['continuity_id'])
    if succession is not None:
        succession.update(succession_state='next-successor-baseline-certified-stable', certification_id=certification['certification_id'])
    return {'state': 'telegram-next-successor-succession-certified', 'certification': certification, 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'certified-next-successor-long-term-monitoring'}


@router.get('/status')
def status() -> dict:
    return {
        'stabilizations': len(_stabilization_store),
        'continuity_observations': sum(len(items) for items in _observation_store.values()),
        'succession_certifications': len(_certification_store),
        'failed_stabilizations': sum(1 for item in _stabilization_store.values() if item.get('stabilization_state') == 'next-successor-stabilization-failed-remediation-required'),
        'external_calls_made': 0,
        'mode': 'next-successor-baseline-stabilization-continuity-observation-succession-certification',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_expired_renewed_successor_restoration_v21_358 import command_center as previous
    return previous().replace('v21.358', 'v21.359').replace(
        'AURON TELEGRAM EXPIRED RENEWED SUCCESSOR RESTORATION COMMAND CENTER',
        'AURON TELEGRAM NEXT SUCCESSOR STABILIZATION COMMAND CENTER',
    )
