from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_regulator_disclosure_delivery_v21_342 import (
    _acknowledgement_store,
    _delivery_store,
    _revocation_store,
)

router = APIRouter(prefix='/auron/demo1/v21.343', tags=['auron-demo1-telegram-post-delivery-compliance-supervision'])

_supervision_store: dict[str, dict] = {}
_incident_store: dict[str, dict] = {}
_confirmation_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM POST DELIVERY COMPLIANCE SUPERVISION'
_OPEN_INCIDENT_PHRASE = 'OPEN AURON TELEGRAM DISCLOSURE INCIDENT'
_RESOLVE_INCIDENT_PHRASE = 'RESOLVE AURON TELEGRAM DISCLOSURE INCIDENT'
_CONFIRM_REVOCATION_PHRASE = 'CONFIRM AURON TELEGRAM DISCLOSURE REVOCATION'


class TelegramPostDeliverySupervisionStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    delivery_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    acknowledgement_sla_hours: int = Field(default=72, ge=1, le=8760)


class TelegramPostDeliveryEvaluateRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    supervision_id: str = Field(min_length=1, max_length=160)
    evaluated_at: datetime | None = None


class TelegramDisclosureIncidentOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    supervision_id: str = Field(min_length=1, max_length=160)
    incident_phrase: str = Field(min_length=1, max_length=320)
    severity: str = Field(pattern='^(low|medium|high|critical)$')
    reason: str = Field(min_length=1, max_length=1500)


class TelegramDisclosureIncidentResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    supervision_id: str = Field(min_length=1, max_length=160)
    resolution_phrase: str = Field(min_length=1, max_length=320)
    resolution: str = Field(min_length=1, max_length=1500)


class TelegramRevocationConfirmationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    supervision_id: str = Field(min_length=1, max_length=160)
    confirmation_phrase: str = Field(min_length=1, max_length=320)
    recipient_reference: str = Field(min_length=1, max_length=300)
    confirmation_statement: str = Field(min_length=1, max_length=1500)


def reset_telegram_post_delivery_compliance_supervision_store() -> None:
    _supervision_store.clear()
    _incident_store.clear()
    _confirmation_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _delivery_by_id(delivery_id: str) -> dict | None:
    return next((item for item in _delivery_store.values() if item.get('delivery_id') == delivery_id), None)


def _supervision_by_id(supervision_id: str) -> dict | None:
    return next((item for item in _supervision_store.values() if item.get('supervision_id') == supervision_id), None)


def _ack_for_delivery(delivery_id: str) -> dict | None:
    return next((item for item in _acknowledgement_store.values() if item.get('delivery_id') == delivery_id), None)


def _revocation_for_delivery(delivery_id: str) -> dict | None:
    return next((item for item in _revocation_store.values() if item.get('delivery_id') == delivery_id), None)


@router.post('/start')
def start_post_delivery_supervision(payload: TelegramPostDeliverySupervisionStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit post-delivery compliance supervision approval required')
    existing = _supervision_store.get(payload.delivery_id)
    if existing is not None:
        return {'state': 'telegram-post-delivery-supervision-already-started', 'supervision': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    delivery = _delivery_by_id(payload.delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail='Telegram regulator disclosure delivery not found')
    checks = {
        'delivery_completed': delivery.get('delivery_state') in {'delivered-awaiting-recipient-acknowledgement', 'delivered-recipient-acknowledged', 'revoked-after-delivery'},
        'delivery_accepted': delivery.get('accepted') is True,
        'delivery_evidence_immutable': delivery.get('immutable') is True and bool(delivery.get('delivery_evidence_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Post-delivery supervision blocked', 'blockers': blockers})
    delivered_at = datetime.fromisoformat(delivery['completed_at'])
    due_at = delivered_at + timedelta(hours=payload.acknowledgement_sla_hours)
    data = {
        'delivery_id': delivery['delivery_id'],
        'disclosure_id': delivery['disclosure_id'],
        'acknowledgement_sla_hours': payload.acknowledgement_sla_hours,
        'acknowledgement_due_at': due_at.isoformat(),
        'delivery_evidence_hash': delivery['delivery_evidence_hash'],
        'checks': checks,
    }
    record = {
        'supervision_id': str(uuid4()),
        **data,
        'supervision_state': 'active-awaiting-acknowledgement',
        'baseline_hash': _hash(data),
        'evaluation_count': 0,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _supervision_store[payload.delivery_id] = record
    return {'state': 'telegram-post-delivery-compliance-supervision-started', 'supervision': record, 'external_calls_made': 0}


@router.post('/evaluate')
def evaluate_post_delivery_supervision(payload: TelegramPostDeliveryEvaluateRequest) -> dict:
    record = _supervision_by_id(payload.supervision_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-delivery supervision record not found')
    delivery = _delivery_by_id(record['delivery_id'])
    acknowledgement = _ack_for_delivery(record['delivery_id'])
    revocation = _revocation_for_delivery(record['delivery_id'])
    evaluated_at = payload.evaluated_at or datetime.now(timezone.utc)
    due_at = datetime.fromisoformat(record['acknowledgement_due_at'])
    checks = {
        'delivery_evidence_unchanged': bool(delivery and delivery.get('delivery_evidence_hash') == record['delivery_evidence_hash']),
        'delivery_still_accepted': bool(delivery and delivery.get('accepted') is True),
        'acknowledgement_valid': bool(acknowledgement and acknowledgement.get('acknowledgement_state') == 'recipient-acknowledgement-recorded'),
        'revocation_recorded': bool(revocation and revocation.get('revocation_state') == 'governed-disclosure-revocation-recorded'),
    }
    overdue = evaluated_at >= due_at and not checks['acknowledgement_valid']
    incident = _incident_store.get(record['supervision_id'])
    incident_open = bool(incident and incident.get('incident_state') == 'open-disclosure-incident')
    if not checks['delivery_evidence_unchanged']:
        state = 'delivery-evidence-drift-incident-required'
    elif incident_open:
        state = 'disclosure-incident-active'
    elif checks['revocation_recorded'] and record['supervision_id'] not in _confirmation_store:
        state = 'revocation-confirmation-pending'
    elif overdue:
        state = 'acknowledgement-sla-breached'
    elif checks['acknowledgement_valid']:
        state = 'recipient-acknowledgement-compliant'
    else:
        state = 'active-awaiting-acknowledgement'
    record.update(supervision_state=state, evaluation_count=record['evaluation_count'] + 1, last_evaluated_at=evaluated_at.isoformat(), latest_checks=checks)
    return {'state': f'telegram-{state}', 'supervision': record, 'acknowledgement_overdue': overdue, 'checks': checks, 'external_calls_made': 0}


@router.post('/incident/open')
def open_disclosure_incident(payload: TelegramDisclosureIncidentOpenRequest) -> dict:
    if payload.incident_phrase != _OPEN_INCIDENT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit disclosure incident approval required')
    record = _supervision_by_id(payload.supervision_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-delivery supervision record not found')
    existing = _incident_store.get(payload.supervision_id)
    if existing and existing.get('incident_state') == 'open-disclosure-incident':
        return {'state': 'telegram-disclosure-incident-already-open', 'incident': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    data = {'supervision_id': record['supervision_id'], 'delivery_id': record['delivery_id'], 'severity': payload.severity, 'reason': payload.reason}
    incident = {'incident_id': str(uuid4()), **data, 'incident_state': 'open-disclosure-incident', 'integrity_hash': _hash(data), 'immutable': True, 'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _incident_store[payload.supervision_id] = incident
    record['supervision_state'] = 'disclosure-incident-active'
    return {'state': 'telegram-disclosure-incident-opened', 'incident': incident, 'external_calls_made': 0}


@router.post('/incident/resolve')
def resolve_disclosure_incident(payload: TelegramDisclosureIncidentResolveRequest) -> dict:
    if payload.resolution_phrase != _RESOLVE_INCIDENT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit disclosure incident resolution required')
    incident = _incident_store.get(payload.supervision_id)
    record = _supervision_by_id(payload.supervision_id)
    if incident is None or record is None:
        raise HTTPException(status_code=404, detail='Telegram disclosure incident not found')
    if incident.get('incident_state') == 'resolved-disclosure-incident':
        return {'state': 'telegram-disclosure-incident-already-resolved', 'incident': incident, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc).isoformat()
    incident.update(incident_state='resolved-disclosure-incident', resolution=payload.resolution, resolved_by=payload.actor, resolved_at=now)
    record['supervision_state'] = 'active-awaiting-acknowledgement'
    return {'state': 'telegram-disclosure-incident-resolved', 'incident': incident, 'supervision': record, 'external_calls_made': 0}


@router.post('/revocation/confirm')
def confirm_disclosure_revocation(payload: TelegramRevocationConfirmationRequest) -> dict:
    if payload.confirmation_phrase != _CONFIRM_REVOCATION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit disclosure revocation confirmation required')
    record = _supervision_by_id(payload.supervision_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram post-delivery supervision record not found')
    existing = _confirmation_store.get(payload.supervision_id)
    if existing is not None:
        return {'state': 'telegram-disclosure-revocation-already-confirmed', 'confirmation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    revocation = _revocation_for_delivery(record['delivery_id'])
    if revocation is None or revocation.get('revocation_state') != 'governed-disclosure-revocation-recorded':
        raise HTTPException(status_code=409, detail='Governed disclosure revocation record required')
    data = {'supervision_id': record['supervision_id'], 'delivery_id': record['delivery_id'], 'revocation_id': revocation['revocation_id'], 'recipient_reference': payload.recipient_reference, 'confirmation_statement': payload.confirmation_statement}
    confirmation = {'confirmation_id': str(uuid4()), **data, 'confirmation_state': 'recipient-revocation-confirmation-recorded', 'integrity_hash': _hash(data), 'immutable': True, 'confirmed_by': payload.actor, 'confirmed_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _confirmation_store[payload.supervision_id] = confirmation
    record['supervision_state'] = 'revocation-confirmed-compliance-closed'
    return {'state': 'telegram-disclosure-revocation-confirmed', 'confirmation': confirmation, 'supervision': record, 'external_calls_made': 0, 'next_layer': 'disclosure-retention-and-recipient-assurance-governance'}


@router.get('/status')
def post_delivery_supervision_status() -> dict:
    records = list(_supervision_store.values())
    return {'supervision_records': len(records), 'awaiting_acknowledgement': sum(1 for item in records if item.get('supervision_state') == 'active-awaiting-acknowledgement'), 'sla_breaches': sum(1 for item in records if item.get('supervision_state') == 'acknowledgement-sla-breached'), 'incidents_open': sum(1 for item in _incident_store.values() if item.get('incident_state') == 'open-disclosure-incident'), 'revocations_confirmed': len(_confirmation_store), 'external_calls_made': 0, 'mode': 'post-delivery-supervision-acknowledgement-sla-revocation-confirmation-incident-governance'}


@router.get('/supervision')
def list_supervision() -> dict:
    return {'count': len(_supervision_store), 'items': list(_supervision_store.values()), 'external_calls_made': 0}


@router.get('/incidents')
def list_incidents() -> dict:
    return {'count': len(_incident_store), 'items': list(_incident_store.values()), 'external_calls_made': 0}


@router.get('/confirmations')
def list_confirmations() -> dict:
    return {'count': len(_confirmation_store), 'items': list(_confirmation_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_regulator_disclosure_delivery_v21_342 import command_center as v21_342_command_center
    return v21_342_command_center().replace('v21.342', 'v21.343').replace(
        'AURON TELEGRAM REGULATOR DISCLOSURE DELIVERY GOVERNANCE COMMAND CENTER',
        'AURON TELEGRAM POST DELIVERY COMPLIANCE SUPERVISION COMMAND CENTER',
    )
