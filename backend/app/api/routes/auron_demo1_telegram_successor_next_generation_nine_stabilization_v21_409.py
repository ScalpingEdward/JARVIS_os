from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_expired_renewed_successor_next_generation_eight_restoration_v21_408 import (
    _succession_store,
)

router = APIRouter(
    prefix='/auron/demo1/v21.409',
    tags=['auron-demo1-telegram-successor-next-generation-nine-stabilization'],
)

_stabilization_store: dict[str, dict] = {}
_observation_store: dict[str, list[dict]] = {}
_certification_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE STABILIZATION'
_OBSERVE_PHRASE = 'OBSERVE AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE CONTINUITY'
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE SUCCESSION'


class StabilizationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    succession_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    stabilization_window_hours: int = Field(default=24, ge=1, le=8760)
    minimum_healthy_observations: int = Field(default=3, ge=1, le=1000)


class ContinuityObservationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    observation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_nine_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    observation_statement: str = Field(min_length=1, max_length=1800)
    observed_at: datetime | None = None


class SuccessionCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    stabilization_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    certification_reference: str = Field(min_length=1, max_length=300)
    certification_statement: str = Field(min_length=1, max_length=1800)
    certified_at: datetime | None = None


def reset_telegram_successor_next_generation_nine_stabilization_store() -> None:
    _stabilization_store.clear()
    _observation_store.clear()
    _certification_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _succession_by_id(succession_id: str) -> dict | None:
    return next((item for item in _succession_store.values() if item.get('succession_id') == succession_id), None)


def _stabilization_by_id(stabilization_id: str) -> dict | None:
    return next((item for item in _stabilization_store.values() if item.get('stabilization_id') == stabilization_id), None)


@router.post('/stabilization/start')
def start_stabilization(payload: StabilizationStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine stabilization approval required')
    existing = _stabilization_store.get(payload.succession_id)
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-stabilization-already-started', 'stabilization': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    succession = _succession_by_id(payload.succession_id)
    if succession is None:
        raise HTTPException(status_code=409, detail='Completed v21.408 successor-next-generation-nine succession required')
    active_hash = succession.get('successor_next_generation_nine_hash')
    checks = {
        'succession_active': succession.get('succession_state') == 'successor-next-generation-nine-baseline-active',
        'succession_immutable': succession.get('immutable') is True and bool(succession.get('integrity_hash')),
        'active_hash_present': bool(active_hash),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Stabilization start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    data = {
        'succession_id': succession['succession_id'],
        'active_successor_next_generation_nine_hash': active_hash,
        'minimum_healthy_observations': payload.minimum_healthy_observations,
        'stabilization_started_at': now.isoformat(),
        'stabilization_ends_at': (now + timedelta(hours=payload.stabilization_window_hours)).isoformat(),
        'checks': checks,
    }
    stabilization = {
        'stabilization_id': str(uuid4()),
        **data,
        'stabilization_state': 'successor-next-generation-nine-stabilization-active',
        'integrity_hash': _hash(data),
        'immutable': True,
        'started_by': payload.actor,
        'external_calls_made': 0,
    }
    _stabilization_store[payload.succession_id] = stabilization
    return {'state': 'telegram-successor-next-generation-nine-stabilization-started', 'stabilization': stabilization, 'external_calls_made': 0}


@router.post('/continuity/observe')
def observe_continuity(payload: ContinuityObservationRequest) -> dict:
    if payload.observation_phrase != _OBSERVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine continuity observation required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Stabilization not found')
    if stabilization.get('stabilization_state') != 'successor-next-generation-nine-stabilization-active':
        raise HTTPException(status_code=409, detail='Active stabilization required')
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    expected_hash = stabilization['active_successor_next_generation_nine_hash']
    hash_matches = payload.observed_successor_next_generation_nine_hash == expected_hash
    healthy = hash_matches and payload.control_state == 'healthy'
    observations = _observation_store.setdefault(stabilization['stabilization_id'], [])
    data = {
        'stabilization_id': stabilization['stabilization_id'],
        'sequence': len(observations) + 1,
        'expected_hash': expected_hash,
        'observed_hash': payload.observed_successor_next_generation_nine_hash,
        'hash_matches': hash_matches,
        'control_state': payload.control_state,
        'healthy': healthy,
        'observation_statement': payload.observation_statement,
    }
    observation = {
        'observation_id': str(uuid4()),
        **data,
        'observation_state': 'successor-next-generation-nine-continuity-healthy' if healthy else 'successor-next-generation-nine-continuity-failed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'observed_by': payload.actor,
        'observed_at': observed_at.isoformat(),
        'external_calls_made': 0,
    }
    observations.append(observation)
    if not healthy:
        stabilization['stabilization_state'] = 'successor-next-generation-nine-stabilization-failed'
        stabilization['failed_observation_id'] = observation['observation_id']
    return {'state': f"telegram-{observation['observation_state']}", 'observation': observation, 'stabilization': stabilization, 'external_calls_made': 0}


@router.post('/succession/certify')
def certify_succession(payload: SuccessionCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit successor-next-generation-nine succession certification required')
    stabilization = _stabilization_by_id(payload.stabilization_id)
    if stabilization is None:
        raise HTTPException(status_code=404, detail='Stabilization not found')
    existing = _certification_store.get(stabilization['stabilization_id'])
    if existing is not None:
        return {'state': 'telegram-successor-next-generation-nine-succession-already-certified', 'certification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certified_at = payload.certified_at or datetime.now(timezone.utc)
    observations = _observation_store.get(stabilization['stabilization_id'], [])
    healthy_observations = [item for item in observations if item.get('healthy') is True]
    checks = {
        'stabilization_active': stabilization.get('stabilization_state') == 'successor-next-generation-nine-stabilization-active',
        'window_elapsed': certified_at >= datetime.fromisoformat(stabilization['stabilization_ends_at']),
        'minimum_observations_met': len(healthy_observations) >= stabilization['minimum_healthy_observations'],
        'all_observations_healthy': bool(observations) and len(healthy_observations) == len(observations),
        'evidence_immutable': all(item.get('immutable') is True and bool(item.get('integrity_hash')) for item in observations),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Succession certification blocked', 'blockers': blockers})
    data = {
        'stabilization_id': stabilization['stabilization_id'],
        'succession_id': stabilization['succession_id'],
        'active_successor_next_generation_nine_hash': stabilization['active_successor_next_generation_nine_hash'],
        'healthy_observation_count': len(healthy_observations),
        'certification_reference': payload.certification_reference,
        'certification_statement': payload.certification_statement,
        'checks': checks,
    }
    certification = {
        'certification_id': str(uuid4()),
        **data,
        'certification_state': 'successor-next-generation-nine-succession-certified-stable',
        'integrity_hash': _hash(data),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': certified_at.isoformat(),
        'external_calls_made': 0,
    }
    _certification_store[stabilization['stabilization_id']] = certification
    stabilization['stabilization_state'] = 'successor-next-generation-nine-certified-stable'
    stabilization['certification_id'] = certification['certification_id']
    return {'state': 'telegram-successor-next-generation-nine-succession-certified-stable', 'certification': certification, 'stabilization': stabilization, 'external_calls_made': 0, 'next_layer': 'certified-successor-next-generation-nine-monitoring-audit-drift-governance'}


@router.get('/status')
def status() -> dict:
    return {
        'stabilizations': len(_stabilization_store),
        'observations': sum(len(items) for items in _observation_store.values()),
        'certifications': len(_certification_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-nine-stabilization-observation-certification-governance',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.409</title></head><body><h1>AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE STABILIZATION COMMAND CENTER</h1><p>Restored-continuity observation and succession certification governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
