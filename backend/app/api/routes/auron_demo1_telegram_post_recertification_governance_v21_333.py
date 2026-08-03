from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_certification_drift_remediation_v21_332 import _recertification_store
from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _baseline_metrics, _certificate_store

router = APIRouter(prefix='/auron/demo1/v21.333', tags=['auron-demo1-telegram-post-recertification-governance'])

_observation_store: dict[str, dict] = {}
_lineage_audit_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM POST RECERTIFICATION OBSERVATION'
_COMPLETE_PHRASE = 'COMPLETE AURON TELEGRAM POST RECERTIFICATION GOVERNANCE'


class TelegramPostRecertificationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certificate_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=260)
    required_stable_observations: int = Field(default=3, ge=1, le=100)
    minimum_reliability_score: float = Field(default=85.0, ge=0.0, le=100.0)


class TelegramPostRecertificationObserveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    governance_id: str = Field(min_length=1, max_length=160)


class TelegramPostRecertificationCompleteRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    governance_id: str = Field(min_length=1, max_length=160)
    completion_phrase: str = Field(min_length=1, max_length=260)


def reset_telegram_post_recertification_governance_store() -> None:
    _observation_store.clear()
    _lineage_audit_store.clear()


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _governance_by_id(governance_id: str) -> dict | None:
    return next((item for item in _observation_store.values() if item.get('governance_id') == governance_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _lineage(certificate: dict) -> dict:
    chain: list[dict] = []
    seen: set[str] = set()
    current = certificate
    valid = True
    while current is not None:
        certificate_id = current.get('certificate_id')
        if not certificate_id or certificate_id in seen:
            valid = False
            break
        seen.add(certificate_id)
        chain.append({
            'certificate_id': certificate_id,
            'supersedes_certificate_id': current.get('supersedes_certificate_id'),
            'certificate_state': current.get('certificate_state'),
            'integrity_hash_present': bool(current.get('integrity_hash')),
            'immutable': bool(current.get('immutable')),
        })
        parent_id = current.get('supersedes_certificate_id')
        current = _certificate_by_id(parent_id) if parent_id else None
        if parent_id and current is None:
            valid = False
            break
    if not all(item['integrity_hash_present'] and item['immutable'] for item in chain):
        valid = False
    return {'valid': valid, 'depth': len(chain), 'chain': chain}


@router.post('/start')
def start_post_recertification_governance(payload: TelegramPostRecertificationStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit post-recertification observation approval required')
    existing = _observation_store.get(payload.certificate_id)
    if existing is not None:
        return {'state': 'telegram-post-recertification-governance-already-started', 'governance': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certificate = _certificate_by_id(payload.certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail='Telegram re-certified service certificate not found')
    if not certificate.get('supersedes_certificate_id'):
        raise HTTPException(status_code=409, detail='Post-recertification governance requires a replacement certificate')
    if not any(item.get('certificate_id') == payload.certificate_id for item in _recertification_store.values()):
        raise HTTPException(status_code=409, detail='Certificate was not issued by controlled v21.332 re-certification')
    chat_id = certificate['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    lineage = _lineage(certificate)
    checks = {
        'certificate_certified': certificate.get('certificate_state') == 'certified',
        'lineage_valid': lineage['valid'],
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Post-recertification governance start blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'governance_id': str(uuid4()),
        'certificate_id': payload.certificate_id,
        'telegram_chat_id': chat_id,
        'required_stable_observations': payload.required_stable_observations,
        'minimum_reliability_score': payload.minimum_reliability_score,
        'stable_observations': 0,
        'degraded_observations': 0,
        'observation_history': [],
        'lineage': lineage,
        'governance_state': 'active-post-recertification-observation',
        'started_by': payload.actor,
        'started_at': now,
        'completed_at': None,
        'external_calls_made': 0,
    }
    _observation_store[payload.certificate_id] = record
    return {'state': 'telegram-post-recertification-governance-started', 'governance': record, 'external_calls_made': 0}


@router.post('/observe')
def observe_post_recertification_governance(payload: TelegramPostRecertificationObserveRequest) -> dict:
    record = _governance_by_id(payload.governance_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-recertification governance not found')
    if record.get('governance_state') != 'active-post-recertification-observation':
        return {'state': 'telegram-post-recertification-governance-already-terminal', 'governance': record, 'idempotent_replay': True, 'external_calls_made': 0}
    certificate = _certificate_by_id(record['certificate_id'])
    if certificate is None:
        raise HTTPException(status_code=404, detail='Governed Telegram certificate not found')
    current = _baseline_metrics(record['telegram_chat_id'])
    lineage = _lineage(certificate)
    stable = (
        lineage['valid']
        and certificate.get('certificate_state') == 'certified'
        and current['runtime_reliability_score'] >= record['minimum_reliability_score']
        and _circuit_store.get(record['telegram_chat_id'], {}).get('state', 'closed') == 'closed'
        and bool(_go_live_store.get(record['telegram_chat_id'], {}).get('continuous_mode_active'))
    )
    now = datetime.now(timezone.utc).isoformat()
    observation = {
        'observation_id': str(uuid4()),
        'metrics': current,
        'lineage_valid': lineage['valid'],
        'stable': stable,
        'observed_by': payload.actor,
        'observed_at': now,
    }
    record['observation_history'].append(observation)
    if stable:
        record['stable_observations'] += 1
        state = 'telegram-post-recertification-stable-observation-recorded'
    else:
        record['degraded_observations'] += 1
        record['governance_state'] = 'governance-review-required'
        state = 'telegram-post-recertification-governance-review-required'
    return {'state': state, 'governance': record, 'external_calls_made': 0}


@router.post('/complete')
def complete_post_recertification_governance(payload: TelegramPostRecertificationCompleteRequest) -> dict:
    if payload.completion_phrase != _COMPLETE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit post-recertification governance completion approval required')
    record = _governance_by_id(payload.governance_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-recertification governance not found')
    if record.get('governance_state') == 'completed-long-horizon-governance':
        return {'state': 'telegram-post-recertification-governance-already-completed', 'governance': record, 'idempotent_replay': True, 'external_calls_made': 0}
    certificate = _certificate_by_id(record['certificate_id'])
    lineage = _lineage(certificate) if certificate else {'valid': False, 'depth': 0, 'chain': []}
    checks = {
        'governance_active': record.get('governance_state') == 'active-post-recertification-observation',
        'stable_observation_threshold_met': record['stable_observations'] >= record['required_stable_observations'],
        'no_degraded_observations': record['degraded_observations'] == 0,
        'lineage_valid': lineage['valid'],
        'service_active': bool(_go_live_store.get(record['telegram_chat_id'], {}).get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(record['telegram_chat_id'], {}).get('state', 'closed') == 'closed',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Post-recertification governance completion blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    audit_payload = {
        'governance_id': record['governance_id'],
        'certificate_id': record['certificate_id'],
        'telegram_chat_id': record['telegram_chat_id'],
        'lineage': lineage,
        'stable_observations': record['stable_observations'],
        'checks': checks,
    }
    audit = {
        'lineage_audit_id': str(uuid4()),
        **audit_payload,
        'integrity_hash': _hash(audit_payload),
        'immutable': True,
        'completed_by': payload.actor,
        'completed_at': now,
        'external_calls_made': 0,
    }
    _lineage_audit_store[record['governance_id']] = audit
    record.update(governance_state='completed-long-horizon-governance', completed_by=payload.actor, completed_at=now, lineage_audit_id=audit['lineage_audit_id'])
    return {'state': 'telegram-post-recertification-governance-completed', 'governance': record, 'lineage_audit': audit, 'external_calls_made': 0}


@router.get('/status')
def post_recertification_governance_status() -> dict:
    items = list(_observation_store.values())
    return {
        'governance_records': len(items),
        'active': sum(1 for item in items if item.get('governance_state') == 'active-post-recertification-observation'),
        'review_required': sum(1 for item in items if item.get('governance_state') == 'governance-review-required'),
        'completed': sum(1 for item in items if item.get('governance_state') == 'completed-long-horizon-governance'),
        'lineage_audits': len(_lineage_audit_store),
        'external_calls_made': 0,
        'mode': 'post-recertification-observation-certificate-lineage-long-horizon-governance',
    }


@router.get('/governance')
def list_post_recertification_governance() -> dict:
    return {'count': len(_observation_store), 'items': list(_observation_store.values()), 'external_calls_made': 0}


@router.get('/lineage-audits')
def list_lineage_audits() -> dict:
    return {'count': len(_lineage_audit_store), 'items': list(_lineage_audit_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_certification_drift_remediation_v21_332 import command_center as v21_332_command_center
    return v21_332_command_center().replace('v21.332', 'v21.333').replace(
        'AURON TELEGRAM CERTIFICATION DRIFT REMEDIATION COMMAND CENTER',
        'AURON TELEGRAM POST RECERTIFICATION GOVERNANCE COMMAND CENTER',
    )
