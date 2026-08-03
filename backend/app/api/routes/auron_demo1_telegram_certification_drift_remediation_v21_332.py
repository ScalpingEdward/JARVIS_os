from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _baseline_metrics, _certificate_store
from app.api.routes.auron_demo1_telegram_slo_monitoring_drift_v21_331 import _drift_store

router = APIRouter(prefix='/auron/demo1/v21.332', tags=['auron-demo1-telegram-certification-drift-remediation'])

_remediation_store: dict[str, dict] = {}
_recertification_store: dict[str, dict] = {}
_ACK_PHRASE = 'ACKNOWLEDGE AURON TELEGRAM CERTIFICATION DRIFT'
_RECERTIFY_PHRASE = 'RECERTIFY AURON TELEGRAM SERVICE'


class TelegramCertificationDriftAcknowledgeRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    drift_id: str = Field(min_length=1, max_length=160)
    acknowledgement_phrase: str = Field(min_length=1, max_length=240)
    remediation_plan: str = Field(min_length=1, max_length=1200)


class TelegramCertificationDriftEvidenceRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    drift_id: str = Field(min_length=1, max_length=160)
    evidence_id: str = Field(min_length=1, max_length=200)
    evidence_summary: str = Field(min_length=1, max_length=1200)


class TelegramServiceRecertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    drift_id: str = Field(min_length=1, max_length=160)
    recertification_phrase: str = Field(min_length=1, max_length=240)
    minimum_reliability_score: float = Field(default=85.0, ge=0.0, le=100.0)


def reset_telegram_certification_drift_remediation_store() -> None:
    _remediation_store.clear()
    _recertification_store.clear()


def _drift(drift_id: str) -> dict:
    item = _drift_store.get(drift_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Telegram certification drift not found')
    return item


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/acknowledge')
def acknowledge_certification_drift(payload: TelegramCertificationDriftAcknowledgeRequest) -> dict:
    if payload.acknowledgement_phrase != _ACK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certification-drift acknowledgement required')
    existing = _remediation_store.get(payload.drift_id)
    if existing is not None:
        return {'state': 'telegram-certification-drift-already-acknowledged', 'remediation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    drift = _drift(payload.drift_id)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        'remediation_id': str(uuid4()),
        'drift_id': payload.drift_id,
        'certificate_id': drift['certificate_id'],
        'telegram_chat_id': drift['telegram_chat_id'],
        'severity': drift['severity'],
        'blockers': list(drift.get('blockers', [])),
        'remediation_plan': payload.remediation_plan,
        'remediation_state': 'acknowledged-awaiting-evidence',
        'acknowledged_by': payload.actor,
        'acknowledged_at': now,
        'external_calls_made': 0,
    }
    _remediation_store[payload.drift_id] = record
    drift.update(acknowledged=True, acknowledged_by=payload.actor, acknowledged_at=now)
    return {'state': 'telegram-certification-drift-acknowledged', 'remediation': record, 'external_calls_made': 0}


@router.post('/evidence')
def submit_remediation_evidence(payload: TelegramCertificationDriftEvidenceRequest) -> dict:
    remediation = _remediation_store.get(payload.drift_id)
    if remediation is None:
        raise HTTPException(status_code=409, detail='Certification drift must be acknowledged before evidence submission')
    if remediation.get('remediation_state') in {'evidence-verified-awaiting-recertification', 'recertified'}:
        return {'state': 'telegram-certification-drift-evidence-already-recorded', 'remediation': remediation, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc).isoformat()
    evidence_payload = {
        'drift_id': payload.drift_id,
        'evidence_id': payload.evidence_id,
        'evidence_summary': payload.evidence_summary,
        'telegram_chat_id': remediation['telegram_chat_id'],
    }
    remediation.update(
        remediation_state='evidence-verified-awaiting-recertification',
        evidence_id=payload.evidence_id,
        evidence_summary=payload.evidence_summary,
        evidence_integrity_hash=_hash(evidence_payload),
        evidence_immutable=True,
        evidence_submitted_by=payload.actor,
        evidence_submitted_at=now,
    )
    return {'state': 'telegram-certification-drift-evidence-recorded', 'remediation': remediation, 'external_calls_made': 0}


@router.post('/recertify')
def recertify_telegram_service(payload: TelegramServiceRecertificationRequest) -> dict:
    if payload.recertification_phrase != _RECERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram service re-certification approval required')
    existing = _recertification_store.get(payload.drift_id)
    if existing is not None:
        return {'state': 'telegram-service-already-recertified', 'certificate': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    drift = _drift(payload.drift_id)
    remediation = _remediation_store.get(payload.drift_id)
    if remediation is None or remediation.get('remediation_state') != 'evidence-verified-awaiting-recertification':
        raise HTTPException(status_code=409, detail='Verified remediation evidence required before re-certification')
    previous = _certificate_by_id(drift['certificate_id'])
    if previous is None:
        raise HTTPException(status_code=404, detail='Suspended Telegram service certificate not found')
    chat_id = drift['telegram_chat_id']
    current = _baseline_metrics(chat_id)
    checks = {
        'previous_certificate_suspended_or_warning': previous.get('certificate_state') in {'suspended-by-drift', 'drift-warning'},
        'reliability_threshold_met': current['runtime_reliability_score'] >= payload.minimum_reliability_score,
        'delivery_recovered': current['delivery_success_rate'] >= previous['slo_baseline']['delivery_success_rate'],
        'lifecycle_recovered': current['lifecycle_completion_rate'] >= previous['slo_baseline']['lifecycle_completion_rate'],
        'dead_letter_rate_recovered': current['dead_letter_rate'] <= previous['slo_baseline']['dead_letter_rate'],
        'evidence_verified': bool(remediation.get('evidence_integrity_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram service re-certification blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    certificate_payload = {
        'supersedes_certificate_id': previous['certificate_id'],
        'drift_id': payload.drift_id,
        'telegram_chat_id': chat_id,
        'metrics': current,
        'checks': checks,
        'remediation_evidence_hash': remediation['evidence_integrity_hash'],
    }
    certificate = {
        'certificate_id': str(uuid4()),
        **certificate_payload,
        'slo_baseline': {
            'delivery_success_rate': current['delivery_success_rate'],
            'lifecycle_completion_rate': current['lifecycle_completion_rate'],
            'queue_completion_rate': current['queue_completion_rate'],
            'dead_letter_rate': current['dead_letter_rate'],
        },
        'runtime_reliability_score': current['runtime_reliability_score'],
        'certificate_state': 'certified',
        'integrity_hash': _hash(certificate_payload),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': now,
        'external_calls_made': 0,
    }
    _recertification_store[payload.drift_id] = certificate
    _certificate_store[f'recertified:{payload.drift_id}'] = certificate
    previous.update(certificate_state='superseded-after-drift-remediation', superseded_by=certificate['certificate_id'], superseded_at=now)
    remediation.update(remediation_state='recertified', recertified_certificate_id=certificate['certificate_id'], recertified_at=now)
    drift.update(resolved=True, resolved_at=now, replacement_certificate_id=certificate['certificate_id'])
    go_live = _go_live_store.get(chat_id)
    if go_live is not None:
        go_live.update(continuous_mode_active=True, go_live_state='recertified-operational-service', service_certificate_id=certificate['certificate_id'])
    circuit = _circuit_store.setdefault(chat_id, {'telegram_chat_id': chat_id})
    circuit.update(state='closed', consecutive_failures=0, reset_at=now, reset_by=payload.actor)
    return {'state': 'telegram-service-recertified', 'certificate': certificate, 'external_calls_made': 0}


@router.get('/status')
def drift_remediation_status() -> dict:
    items = list(_remediation_store.values())
    return {
        'remediations': len(items),
        'awaiting_evidence': sum(1 for item in items if item.get('remediation_state') == 'acknowledged-awaiting-evidence'),
        'awaiting_recertification': sum(1 for item in items if item.get('remediation_state') == 'evidence-verified-awaiting-recertification'),
        'recertified': sum(1 for item in items if item.get('remediation_state') == 'recertified'),
        'external_calls_made': 0,
        'mode': 'acknowledged-evidence-gated-controlled-recertification',
    }


@router.get('/remediations')
def list_drift_remediations() -> dict:
    items = sorted(_remediation_store.values(), key=lambda item: item['acknowledged_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_slo_monitoring_drift_v21_331 import command_center as v21_331_command_center
    return v21_331_command_center().replace('v21.331', 'v21.332').replace(
        'AURON TELEGRAM CONTINUOUS SLO MONITORING DRIFT COMMAND CENTER',
        'AURON TELEGRAM CERTIFICATION DRIFT REMEDIATION COMMAND CENTER',
    )
