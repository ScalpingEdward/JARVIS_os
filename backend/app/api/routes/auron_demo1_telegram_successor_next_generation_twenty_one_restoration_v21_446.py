from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_twenty_continuity_v21_445 import _renewal_store
from app.api.routes.auron_demo1_telegram_successor_next_generation_twenty_monitoring_v21_444 import _monitor_store

router = APIRouter(
    prefix='/auron/demo1/v21.446',
    tags=['auron-demo1-telegram-successor-next-generation-twenty-one-restoration'],
)

_restoration_store: dict[str, dict] = {}
_activation_store: dict[str, dict] = {}
_succession_store: dict[str, dict] = {}

_RESTORE_PHRASE = 'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY ONE'
_ACTIVATE_PHRASE = 'ACTIVATE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY ONE'
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWENTY ONE SUCCESSION'


class RestorationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    renewal_request_id: str = Field(min_length=1, max_length=160)
    restoration_phrase: str = Field(min_length=1, max_length=320)
    proposed_successor_next_generation_twenty_one_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    restoration_reference: str = Field(min_length=1, max_length=300)
    restoration_statement: str = Field(min_length=1, max_length=1800)


class ActivationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    restoration_id: str = Field(min_length=1, max_length=160)
    activation_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_twenty_one_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    activation_reference: str = Field(min_length=1, max_length=300)
    activation_statement: str = Field(min_length=1, max_length=1800)


class SuccessionCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    activation_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    certification_reference: str = Field(min_length=1, max_length=300)
    certification_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_twenty_one_restoration_store() -> None:
    _restoration_store.clear()
    _activation_store.clear()
    _succession_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _find(store: dict[str, dict], key: str, value: str) -> dict | None:
    return next((item for item in store.values() if item.get(key) == value), None)


@router.post('/restoration/prepare')
def prepare_restoration(payload: RestorationRequest) -> dict:
    if payload.restoration_phrase != _RESTORE_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-one restoration approval required')
    existing = _restoration_store.get(payload.renewal_request_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-one-restoration-already-prepared', 'restoration': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    renewal = _find(_renewal_store, 'renewal_request_id', payload.renewal_request_id)
    if renewal is None:
        raise HTTPException(404, 'Immutable successor-next-generation-twenty renewal request not found')
    monitoring = _find(_monitor_store, 'monitoring_id', renewal['monitoring_id'])
    checks = {
        'renewal_requested': renewal.get('renewal_state') == 'successor-next-generation-twenty-renewal-requested',
        'renewal_immutable': renewal.get('immutable') is True and bool(renewal.get('integrity_hash')),
        'monitoring_requires_renewal': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-twenty-renewal-required',
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-one restoration blocked', 'blockers': blockers})
    data = {
        'renewal_request_id': renewal['renewal_request_id'],
        'monitoring_id': renewal['monitoring_id'],
        'predecessor_baseline_id': renewal['baseline_id'],
        'proposed_successor_next_generation_twenty_one_hash': payload.proposed_successor_next_generation_twenty_one_hash,
        'restoration_reference': payload.restoration_reference,
        'restoration_statement': payload.restoration_statement,
        'checks': checks,
    }
    restoration = {
        'restoration_id': str(uuid4()), **data,
        'restoration_state': 'successor-next-generation-twenty-one-restored-pending-activation',
        'integrity_hash': _hash(data), 'immutable': True,
        'restored_by': payload.actor, 'restored_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _restoration_store[payload.renewal_request_id] = restoration
    monitoring['monitoring_state'] = 'successor-next-generation-twenty-one-activation-pending'
    monitoring['successor_next_generation_twenty_one_restoration_id'] = restoration['restoration_id']
    return {'state': 'telegram-successor-next-generation-twenty-one-restored-pending-activation', 'restoration': restoration, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/activation/execute')
def activate_successor(payload: ActivationRequest) -> dict:
    if payload.activation_phrase != _ACTIVATE_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-one activation approval required')
    existing = _activation_store.get(payload.restoration_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-one-already-activated', 'activation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    restoration = _find(_restoration_store, 'restoration_id', payload.restoration_id)
    if restoration is None:
        raise HTTPException(404, 'Stable successor-next-generation-twenty-one restoration not found')
    monitoring = _find(_monitor_store, 'monitoring_id', restoration['monitoring_id'])
    expected = restoration['proposed_successor_next_generation_twenty_one_hash']
    checks = {
        'restoration_ready': restoration.get('restoration_state') == 'successor-next-generation-twenty-one-restored-pending-activation',
        'restoration_immutable': restoration.get('immutable') is True and bool(restoration.get('integrity_hash')),
        'monitoring_pending_activation': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-twenty-one-activation-pending',
        'hash_matches': payload.observed_successor_next_generation_twenty_one_hash == expected,
        'controls_healthy': payload.control_state == 'healthy',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-one activation blocked', 'blockers': blockers})
    data = {
        'restoration_id': restoration['restoration_id'],
        'monitoring_id': restoration['monitoring_id'],
        'active_successor_next_generation_twenty_one_hash': expected,
        'activation_reference': payload.activation_reference,
        'activation_statement': payload.activation_statement,
        'checks': checks,
    }
    activation = {
        'activation_id': str(uuid4()), **data,
        'activation_state': 'successor-next-generation-twenty-one-activated-controlled',
        'integrity_hash': _hash(data), 'immutable': True,
        'activated_by': payload.actor, 'activated_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _activation_store[payload.restoration_id] = activation
    restoration['restoration_state'] = 'successor-next-generation-twenty-one-restored-and-activated'
    restoration['activation_id'] = activation['activation_id']
    monitoring['monitoring_state'] = 'successor-next-generation-twenty-one-succession-certification-pending'
    monitoring['active_successor_next_generation_twenty_one_hash'] = expected
    monitoring['successor_next_generation_twenty_one_activation_id'] = activation['activation_id']
    return {'state': 'telegram-successor-next-generation-twenty-one-activated-controlled', 'activation': activation, 'monitoring': monitoring, 'external_calls_made': 0}


@router.post('/succession/certify')
def certify_succession(payload: SuccessionCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-twenty-one succession certification required')
    existing = _succession_store.get(payload.activation_id)
    if existing:
        return {'state': 'telegram-successor-next-generation-twenty-one-succession-already-certified', 'certification': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    activation = _find(_activation_store, 'activation_id', payload.activation_id)
    if activation is None:
        raise HTTPException(404, 'Controlled successor-next-generation-twenty-one activation not found')
    monitoring = _find(_monitor_store, 'monitoring_id', activation['monitoring_id'])
    checks = {
        'activation_controlled': activation.get('activation_state') == 'successor-next-generation-twenty-one-activated-controlled',
        'activation_immutable': activation.get('immutable') is True and bool(activation.get('integrity_hash')),
        'monitoring_pending_certification': monitoring is not None and monitoring.get('monitoring_state') == 'successor-next-generation-twenty-one-succession-certification-pending',
        'active_hash_aligned': monitoring is not None and monitoring.get('active_successor_next_generation_twenty_one_hash') == activation.get('active_successor_next_generation_twenty_one_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(409, {'message': 'Successor-next-generation-twenty-one succession certification blocked', 'blockers': blockers})
    data = {
        'activation_id': activation['activation_id'],
        'monitoring_id': activation['monitoring_id'],
        'active_successor_next_generation_twenty_one_hash': activation['active_successor_next_generation_twenty_one_hash'],
        'certification_reference': payload.certification_reference,
        'certification_statement': payload.certification_statement,
        'checks': checks,
    }
    certification = {
        'certification_id': str(uuid4()), **data,
        'certification_state': 'successor-next-generation-twenty-one-succession-certified-stable',
        'integrity_hash': _hash(data), 'immutable': True,
        'certified_by': payload.actor, 'certified_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _succession_store[payload.activation_id] = certification
    monitoring['monitoring_state'] = 'certified-successor-next-generation-twenty-one-monitoring-pending'
    monitoring['successor_next_generation_twenty_one_certification_id'] = certification['certification_id']
    monitoring.pop('expiry_id', None)
    return {
        'state': 'telegram-successor-next-generation-twenty-one-succession-certified-stable',
        'certification': certification, 'monitoring': monitoring, 'external_calls_made': 0,
        'next_layer': 'successor-next-generation-twenty-one-monitoring-drift-renewed-baseline-certification',
    }


@router.get('/status')
def status() -> dict:
    return {
        'restorations': len(_restoration_store),
        'activations': len(_activation_store),
        'certifications': len(_succession_store),
        'external_calls_made': 0,
        'mode': 'successor-next-generation-twenty-one-restoration-activation-succession',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><head><title>AURON v21.446</title></head><body><h1>AURON SUCCESSOR NEXT GENERATION TWENTY ONE COMMAND CENTER</h1><p>Restoration, controlled activation and succession governance.</p><p>Safe mode: no Telegram API call, no provider execution, no outbound message.</p></body></html>'
