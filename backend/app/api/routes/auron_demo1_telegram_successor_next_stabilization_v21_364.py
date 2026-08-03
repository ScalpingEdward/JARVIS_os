from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_expired_renewed_next_successor_restoration_v21_363 import (
    _restoration_store,
    _succession_store,
)
from app.api.routes.auron_demo1_telegram_renewed_next_successor_continuity_v21_362 import _continuity_store

router = APIRouter(prefix='/auron/demo1/v21.364', tags=['auron-demo1-telegram-successor-next-stabilization'])
_stabilization_store: dict[str, dict] = {}
_observation_store: dict[str, list[dict]] = {}
_certification_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM SUCCESSOR NEXT STABILIZATION'
_OBSERVE_PHRASE = 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT CONTINUITY'
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT SUCCESSION'


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
    observed_successor_next_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
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


def reset_telegram_successor_next_stabilization_store() -> None:
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
        raise HTTPException(status_code=403, detail='Explicit successor-next stabilization approval required')
    existing = _stabilization_store.get(payload.continuity_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-stabilization-already-started', 'stabilization': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    continuity = _continuity_by_id(payload.continuity_id)
    succession = _succession_store.get(payload.continuity_id)
    restoration = _restoration_store.get(payload.continuity_id)
    if continuity is None or succession is None or restoration is None:
        raise HTTPException(status_code=409, detail='Completed v21.363 restoration and successor-next baseline required')
    checks = {
        'succession_active': succession.get('succession_state') == 'successor-next-baseline-active',
        'succession_immutable': succession.get('immutable') is True and bool(succession.get('integrity_hash')),
        'restoration_complete': restoration.get('restoration_state') == 'renewed-next-successor-continuity-restored-awaiting-successor-next-baseline',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'continuity_active': continuity.get('continuity_state') == 'renewed-next-successor-continuity-active',
        'successor_hash_active': succession.get('successor_next_hash') == continuity.get('active_baseline_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-next stabilization blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'continuity_id': continuity['continuity_id'],
        'succession_id': succession['succession_id'],
        'restoration_id': restoration['restoration_id'],
        'successor_next_hash': succession['successor_next_hash'],
        'stabilization_hours': payload.stabilization_hours,
        'minimum_observations': payload.minimum_observations,
        'stabilization_ends_at': (now + timedelta(hours=payload.stabilization_hours)).isoformat(),
        'checks': checks,
    }
    stabilization = {
        'stabilization_id': str(uuid4()), **data,
        'stabilization_state': 'successor-next-stabilization-active',
        'observation_count': 0, 'healthy_observation_count': 0,
        'integrity_hash': _hash(data), 'immutable': True,
        'started_by': payload.actor, 'started_at': now.isoformat(), 'external_calls_made': 0,
    }
    _stabilization_store[payload.continuity_id] = stabilization
    continuity['continuity_state'] = 'successor-next-stabilization-active'
    return {'state': 'telegram-successor-next-stabilization-started', 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/continuity/observe')
def observe_continuity(payload: ContinuityObservationRequest) -> dict:
    if payload.observation_phrase != _OBSERVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next continuity observation required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Successor-next stabilization not found')
    if stabilization.get('stabilization_state') not in {'successor-next-stabilization-active', 'successor-next-observation-complete'}:
        raise HTTPException(status_code=409, detail='Successor-next stabilization is not open for observation')
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    observations = _observation_store.setdefault(stabilization['stabilization_id'], [])
    sequence = len(observations) + 1
    hash_matches = payload.observed_successor_next_hash == stabilization['successor_next_hash']
    healthy = hash_matches and payload.continuity_state == 'healthy'
    data = {
        'stabilization_id': stabilization['stabilization_id'], 'continuity_id': stabilization['continuity_id'],
        'sequence': sequence, 'expected_successor_next_hash': stabilization['successor_next_hash'],
        'observed_successor_next_hash': payload.observed_successor_next_hash, 'hash_matches': hash_matches,
        'continuity_state': payload.continuity_state, 'healthy': healthy, 'statement': payload.statement,
    }
    observation = {
        'observation_id': str(uuid4()), **data,
        'observation_state': 'successor-next-continuity-healthy' if healthy else 'successor-next-instability-detected',
        'integrity_hash': _hash(data), 'immutable': True,
        'observed_by': payload.actor, 'observed_at': observed_at.isoformat(), 'external_calls_made': 0,
    }
    observations.append(observation)
    healthy_count = sum(1 for item in observations if item.get('healthy') is True)
    stabilization.update(observation_count=len(observations), healthy_observation_count=healthy_count, last_observation_id=observation['observation_id'])
    continuity = _continuity_by_id(stabilization['continuity_id'])
    if not healthy:
        stabilization['stabilization_state'] = 'successor-next-stabilization-failed-remediation-required'
        if continuity is not None:
            continuity['continuity_state'] = 'successor-next-instability-remediation-required'
    elif healthy_count >= stabilization['minimum_observations']:
        stabilization['stabilization_state'] = 'successor-next-observation-complete'
    return {'state': f"telegram-{observation['observation_state']}", 'observation': observation, 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0}


@router.post('/succession/certify')
def certify_succession(payload: SuccessionCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next succession certification required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Successor-next stabilization not found')
    existing = _certification_store.get(stabilization['stabilization_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-succession-already-certified', 'certification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certified_at = payload.certified_at or datetime.now(timezone.utc)
    observations = _observation_store.get(stabilization['stabilization_id'], [])
    checks = {
        'observation_complete': stabilization.get('stabilization_state') == 'successor-next-observation-complete',
        'stabilization_window_elapsed': certified_at >= datetime.fromisoformat(stabilization['stabilization_ends_at']),
        'minimum_observations_met': stabilization.get('healthy_observation_count', 0) >= stabilization['minimum_observations'],
        'all_observations_healthy': bool(observations) and all(item.get('healthy') is True for item in observations),
        'successor_hash_consistent': all(item.get('observed_successor_next_hash') == stabilization['successor_next_hash'] for item in observations),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Successor-next succession certification blocked', 'blockers': blockers})
    data = {
        'stabilization_id': stabilization['stabilization_id'], 'continuity_id': stabilization['continuity_id'],
        'succession_id': stabilization['succession_id'], 'successor_next_hash': stabilization['successor_next_hash'],
        'observation_count': len(observations), 'certification_reference': payload.certification_reference,
        'certification_statement': payload.certification_statement, 'checks': checks,
    }
    certification = {
        'certification_id': str(uuid4()), **data,
        'certification_state': 'successor-next-succession-certified-stable',
        'integrity_hash': _hash(data), 'immutable': True,
        'certified_by': payload.actor, 'certified_at': certified_at.isoformat(), 'external_calls_made': 0,
    }
    _certification_store[stabilization['stabilization_id']] = certification
    stabilization['stabilization_state'] = 'successor-next-stabilization-certified-closed'
    continuity = _continuity_by_id(stabilization['continuity_id'])
    if continuity is not None:
        continuity.update(continuity_state='renewed-next-successor-continuity-active', last_successor_next_certification_id=certification['certification_id'])
    succession = _succession_store.get(stabilization['continuity_id'])
    if succession is not None:
        succession.update(succession_state='successor-next-baseline-certified-stable', certification_id=certification['certification_id'])
    return {'state': 'telegram-successor-next-succession-certified', 'certification': certification, 'stabilization': stabilization, 'continuity': continuity, 'external_calls_made': 0, 'next_layer': 'certified-successor-next-long-term-monitoring'}


@router.get('/status')
def status() -> dict:
    return {
        'stabilizations': len(_stabilization_store),
        'continuity_observations': sum(len(items) for items in _observation_store.values()),
        'succession_certifications': len(_certification_store),
        'failed_stabilizations': sum(1 for item in _stabilization_store.values() if item.get('stabilization_state') == 'successor-next-stabilization-failed-remediation-required'),
        'external_calls_made': 0,
        'mode': 'successor-next-baseline-stabilization-continuity-observation-succession-certification',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_expired_renewed_next_successor_restoration_v21_363 import command_center as previous
    return previous().replace('v21.363', 'v21.364').replace(
        'AURON TELEGRAM EXPIRED RENEWED NEXT SUCCESSOR RESTORATION COMMAND CENTER',
        'AURON TELEGRAM SUCCESSOR NEXT STABILIZATION COMMAND CENTER',
    )
