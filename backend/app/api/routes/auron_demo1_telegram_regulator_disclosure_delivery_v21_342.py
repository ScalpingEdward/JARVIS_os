from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_compliance_ledger_disclosure_v21_341 import (
    _disclosure_store,
    _ledger_store,
    _package_store,
)

router = APIRouter(prefix='/auron/demo1/v21.342', tags=['auron-demo1-telegram-regulator-disclosure-delivery'])

_delivery_store: dict[str, dict] = {}
_acknowledgement_store: dict[str, dict] = {}
_revocation_store: dict[str, dict] = {}
_EXECUTE_PHRASE = 'EXECUTE AURON TELEGRAM REGULATOR DISCLOSURE DELIVERY'
_ACK_PHRASE = 'ACKNOWLEDGE AURON TELEGRAM REGULATOR DISCLOSURE RECEIPT'
_REVOKE_PHRASE = 'REVOKE AURON TELEGRAM REGULATOR DISCLOSURE'


class TelegramRegulatorDisclosureDeliveryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    disclosure_id: str = Field(min_length=1, max_length=160)
    execution_phrase: str = Field(min_length=1, max_length=320)
    delivery_channel: str = Field(default='controlled-regulator-gateway', min_length=1, max_length=120)


class TelegramRegulatorAcknowledgementRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    delivery_id: str = Field(min_length=1, max_length=160)
    acknowledgement_phrase: str = Field(min_length=1, max_length=320)
    recipient_reference: str = Field(min_length=1, max_length=300)
    acknowledgement_reference: str = Field(min_length=1, max_length=300)


class TelegramRegulatorDisclosureRevocationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    delivery_id: str = Field(min_length=1, max_length=160)
    revocation_phrase: str = Field(min_length=1, max_length=320)
    reason: str = Field(min_length=1, max_length=1500)


def reset_telegram_regulator_disclosure_delivery_store() -> None:
    _delivery_store.clear()
    _acknowledgement_store.clear()
    _revocation_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _disclosure_by_id(disclosure_id: str) -> dict | None:
    return next((item for item in _disclosure_store.values() if item.get('disclosure_id') == disclosure_id), None)


def _package_by_id(package_id: str) -> dict | None:
    return next((item for item in _package_store.values() if item.get('package_id') == package_id), None)


def _ledger_by_id(ledger_id: str) -> dict | None:
    return next((item for item in _ledger_store.values() if item.get('ledger_id') == ledger_id), None)


def _delivery_by_id(delivery_id: str) -> dict | None:
    return next((item for item in _delivery_store.values() if item.get('delivery_id') == delivery_id), None)


def _runtime_enabled() -> bool:
    return os.getenv('REGULATOR_DISCLOSURE_DELIVERY_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _default_transport(_: dict) -> tuple[bool, str | None, str | None]:
    return False, None, 'No regulator disclosure transport adapter configured'


def execute_regulator_disclosure_delivery(
    payload: TelegramRegulatorDisclosureDeliveryRequest,
    transport: Callable[[dict], tuple[bool, str | None, str | None]] | None = None,
) -> dict:
    if payload.execution_phrase != _EXECUTE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit regulator disclosure delivery approval required')
    existing = _delivery_store.get(payload.disclosure_id)
    if existing is not None:
        return {'state': 'telegram-regulator-disclosure-delivery-already-executed', 'delivery': existing, 'idempotent_replay': True, 'external_calls_made': existing['external_calls_made']}
    disclosure = _disclosure_by_id(payload.disclosure_id)
    if disclosure is None:
        raise HTTPException(status_code=404, detail='Authorized regulator disclosure not found')
    package = _package_by_id(disclosure['package_id'])
    ledger = _ledger_by_id(package['ledger_id']) if package else None
    checks = {
        'disclosure_authorized': disclosure.get('disclosure_state') == 'authorized-no-transport-executed',
        'authorization_hash_present': bool(disclosure.get('authorization_hash')) and disclosure.get('immutable') is True,
        'package_authorized': bool(package and package.get('package_state') == 'controlled-disclosure-authorized'),
        'package_signature_present': bool(package and package.get('signature_hash')),
        'ledger_hash_present': bool(ledger and ledger.get('ledger_hash')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Regulator disclosure delivery blocked', 'blockers': blockers})
    if transport is None and not _runtime_enabled():
        raise HTTPException(status_code=409, detail='Regulator disclosure delivery runtime is disabled')

    envelope = {
        'disclosure_id': disclosure['disclosure_id'],
        'package_id': package['package_id'],
        'ledger_id': ledger['ledger_id'],
        'recipient': disclosure['recipient'],
        'purpose': disclosure['purpose'],
        'scope': disclosure['scope'],
        'ledger_hash': ledger['ledger_hash'],
        'signature_hash': package['signature_hash'],
        'authorization_hash': disclosure['authorization_hash'],
        'delivery_channel': payload.delivery_channel,
    }
    call = transport or _default_transport
    started_at = datetime.now(timezone.utc).isoformat()
    accepted, provider_reference, provider_error = call(envelope)
    completed_at = datetime.now(timezone.utc).isoformat()
    delivery_payload = {
        'disclosure_id': disclosure['disclosure_id'],
        'package_id': package['package_id'],
        'ledger_id': ledger['ledger_id'],
        'recipient': disclosure['recipient'],
        'delivery_channel': payload.delivery_channel,
        'envelope_hash': _hash(envelope),
        'accepted': accepted,
        'provider_reference': provider_reference,
        'provider_error': provider_error,
        'checks': checks,
    }
    delivery = {
        'delivery_id': str(uuid4()),
        **delivery_payload,
        'delivery_state': 'delivered-awaiting-recipient-acknowledgement' if accepted else 'delivery-failed-no-disclosure-acknowledgement',
        'integrity_hash': _hash(delivery_payload),
        'immutable': True,
        'executed_by': payload.actor,
        'started_at': started_at,
        'completed_at': completed_at,
        'outbound_disclosures_sent': 1 if accepted else 0,
        'external_calls_made': 1,
    }
    _delivery_store[payload.disclosure_id] = delivery
    disclosure['disclosure_state'] = 'delivered-awaiting-recipient-acknowledgement' if accepted else 'authorized-delivery-failed'
    return {'state': 'telegram-regulator-disclosure-delivery-completed', 'delivery': delivery, 'external_calls_made': 1}


@router.post('/delivery/execute')
def execute_delivery_route(payload: TelegramRegulatorDisclosureDeliveryRequest) -> dict:
    return execute_regulator_disclosure_delivery(payload)


@router.post('/acknowledgement')
def acknowledge_regulator_disclosure(payload: TelegramRegulatorAcknowledgementRequest) -> dict:
    if payload.acknowledgement_phrase != _ACK_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit regulator disclosure acknowledgement approval required')
    existing = _acknowledgement_store.get(payload.delivery_id)
    if existing is not None:
        return {'state': 'telegram-regulator-disclosure-already-acknowledged', 'acknowledgement': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    delivery = _delivery_by_id(payload.delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail='Regulator disclosure delivery not found')
    checks = {
        'delivery_accepted': delivery.get('accepted') is True,
        'awaiting_acknowledgement': delivery.get('delivery_state') == 'delivered-awaiting-recipient-acknowledgement',
        'delivery_integrity_present': bool(delivery.get('integrity_hash')) and delivery.get('immutable') is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Recipient acknowledgement blocked', 'blockers': blockers})
    data = {
        'delivery_id': delivery['delivery_id'],
        'disclosure_id': delivery['disclosure_id'],
        'recipient_reference': payload.recipient_reference,
        'acknowledgement_reference': payload.acknowledgement_reference,
        'delivery_integrity_hash': delivery['integrity_hash'],
        'checks': checks,
    }
    acknowledgement = {
        'acknowledgement_id': str(uuid4()),
        **data,
        'acknowledgement_state': 'recipient-acknowledgement-receipt-committed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'acknowledged_by': payload.actor,
        'acknowledged_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _acknowledgement_store[payload.delivery_id] = acknowledgement
    delivery.update(delivery_state='delivered-recipient-acknowledged', acknowledgement_id=acknowledgement['acknowledgement_id'])
    return {'state': 'telegram-regulator-disclosure-recipient-acknowledged', 'acknowledgement': acknowledgement, 'external_calls_made': 0}


@router.post('/revocation')
def revoke_regulator_disclosure(payload: TelegramRegulatorDisclosureRevocationRequest) -> dict:
    if payload.revocation_phrase != _REVOKE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit regulator disclosure revocation approval required')
    existing = _revocation_store.get(payload.delivery_id)
    if existing is not None:
        return {'state': 'telegram-regulator-disclosure-already-revoked', 'revocation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    delivery = _delivery_by_id(payload.delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail='Regulator disclosure delivery not found')
    if delivery.get('delivery_state') == 'delivery-failed-no-disclosure-acknowledgement':
        raise HTTPException(status_code=409, detail='Failed disclosure delivery does not require revocation')
    data = {
        'delivery_id': delivery['delivery_id'],
        'disclosure_id': delivery['disclosure_id'],
        'reason': payload.reason,
        'previous_delivery_state': delivery['delivery_state'],
        'provider_reference': delivery.get('provider_reference'),
    }
    revocation = {
        'revocation_id': str(uuid4()),
        **data,
        'revocation_state': 'disclosure-revoked-governance-recorded',
        'integrity_hash': _hash(data),
        'immutable': True,
        'revoked_by': payload.actor,
        'revoked_at': datetime.now(timezone.utc).isoformat(),
        'transport_recall_guaranteed': False,
        'external_calls_made': 0,
    }
    _revocation_store[payload.delivery_id] = revocation
    delivery.update(delivery_state='revoked-after-delivery', revocation_id=revocation['revocation_id'])
    disclosure = _disclosure_by_id(delivery['disclosure_id'])
    if disclosure is not None:
        disclosure['disclosure_state'] = 'revoked-after-delivery'
    return {'state': 'telegram-regulator-disclosure-revoked', 'revocation': revocation, 'external_calls_made': 0, 'next_layer': 'disclosure-post-delivery-compliance-supervision'}


@router.get('/status')
def regulator_disclosure_delivery_status() -> dict:
    deliveries = list(_delivery_store.values())
    return {
        'runtime_enabled': _runtime_enabled(),
        'deliveries': len(deliveries),
        'accepted_deliveries': sum(1 for item in deliveries if item.get('accepted')),
        'failed_deliveries': sum(1 for item in deliveries if not item.get('accepted')),
        'acknowledgements': len(_acknowledgement_store),
        'revocations': len(_revocation_store),
        'outbound_disclosures_sent': sum(item.get('outbound_disclosures_sent', 0) for item in deliveries),
        'external_calls_made': sum(item.get('external_calls_made', 0) for item in deliveries),
        'mode': 'controlled-regulator-disclosure-delivery-acknowledgement-revocation-governance',
    }


@router.get('/deliveries')
def list_deliveries() -> dict:
    return {'count': len(_delivery_store), 'items': list(_delivery_store.values())}


@router.get('/acknowledgements')
def list_acknowledgements() -> dict:
    return {'count': len(_acknowledgement_store), 'items': list(_acknowledgement_store.values())}


@router.get('/revocations')
def list_revocations() -> dict:
    return {'count': len(_revocation_store), 'items': list(_revocation_store.values())}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_compliance_ledger_disclosure_v21_341 import command_center as v21_341_command_center
    return v21_341_command_center().replace('v21.341', 'v21.342').replace(
        'AURON TELEGRAM COMPLIANCE LEDGER DISCLOSURE COMMAND CENTER',
        'AURON TELEGRAM REGULATOR DISCLOSURE DELIVERY COMMAND CENTER',
    )
