from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_long_term_compliance_monitoring_v21_340 import (
    _exception_store,
    _monitoring_store,
    _reattestation_store,
)

router = APIRouter(prefix='/auron/demo1/v21.341', tags=['auron-demo1-telegram-compliance-ledger-disclosure'])

_ledger_store: dict[str, dict] = {}
_package_store: dict[str, dict] = {}
_disclosure_store: dict[str, dict] = {}
_EXPORT_PHRASE = 'EXPORT AURON TELEGRAM COMPLIANCE EVIDENCE LEDGER'
_SIGN_PHRASE = 'SIGN AURON TELEGRAM REGULATOR REPORTING PACKAGE'
_DISCLOSE_PHRASE = 'AUTHORIZE AURON TELEGRAM CONTROLLED REGULATOR DISCLOSURE'


class TelegramComplianceLedgerExportRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    export_phrase: str = Field(min_length=1, max_length=320)


class TelegramRegulatorPackageSignRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    ledger_id: str = Field(min_length=1, max_length=160)
    sign_phrase: str = Field(min_length=1, max_length=320)
    regulator: str = Field(min_length=1, max_length=300)
    reporting_reference: str = Field(min_length=1, max_length=300)


class TelegramControlledDisclosureRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    package_id: str = Field(min_length=1, max_length=160)
    disclosure_phrase: str = Field(min_length=1, max_length=320)
    recipient: str = Field(min_length=1, max_length=300)
    purpose: str = Field(min_length=1, max_length=1200)
    scope: list[str] = Field(min_length=1, max_length=30)


def reset_telegram_compliance_ledger_disclosure_store() -> None:
    _ledger_store.clear()
    _package_store.clear()
    _disclosure_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _ledger_by_id(ledger_id: str) -> dict | None:
    return next((item for item in _ledger_store.values() if item.get('ledger_id') == ledger_id), None)


def _package_by_id(package_id: str) -> dict | None:
    return next((item for item in _package_store.values() if item.get('package_id') == package_id), None)


@router.post('/ledger/export')
def export_compliance_ledger(payload: TelegramComplianceLedgerExportRequest) -> dict:
    if payload.export_phrase != _EXPORT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit compliance ledger export approval required')
    existing = _ledger_store.get(payload.monitoring_id)
    if existing is not None:
        return {'state': 'telegram-compliance-ledger-already-exported', 'ledger': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    monitoring = _monitoring_by_id(payload.monitoring_id)
    if monitoring is None:
        raise HTTPException(status_code=404, detail='Telegram long-term compliance monitoring record not found')
    exception = _exception_store.get(payload.monitoring_id)
    checks = {
        'monitoring_active_or_due': monitoring.get('monitoring_state') in {'active-compliance-monitoring', 'periodic-reattestation-due'},
        'no_open_regulatory_exception': not bool(exception and exception.get('exception_state') == 'open-regulatory-exception'),
        'baseline_evidence_present': bool(monitoring.get('baseline_evidence_hash')),
        'monitoring_immutable': monitoring.get('immutable') is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Compliance ledger export blocked', 'blockers': blockers})
    reattestations = list(_reattestation_store.get(payload.monitoring_id, []))
    entries = [{
        'entry_type': 'monitoring-baseline',
        'monitoring_id': monitoring['monitoring_id'],
        'baseline_evidence_hash': monitoring['baseline_evidence_hash'],
        'started_at': monitoring['started_at'],
    }]
    entries.extend({
        'entry_type': 'periodic-reattestation',
        'sequence': item['sequence'],
        'reattestation_id': item['reattestation_id'],
        'integrity_hash': item['integrity_hash'],
        'reattested_at': item['reattested_at'],
    } for item in reattestations)
    ledger_payload = {'monitoring_id': monitoring['monitoring_id'], 'audit_id': monitoring['audit_id'], 'entries': entries, 'checks': checks}
    ledger = {
        'ledger_id': str(uuid4()),
        **ledger_payload,
        'ledger_state': 'immutable-compliance-evidence-ledger-exported',
        'ledger_hash': _hash(ledger_payload),
        'entry_count': len(entries),
        'immutable': True,
        'exported_by': payload.actor,
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _ledger_store[payload.monitoring_id] = ledger
    return {'state': 'telegram-compliance-evidence-ledger-exported', 'ledger': ledger, 'external_calls_made': 0}


@router.post('/package/sign')
def sign_regulator_package(payload: TelegramRegulatorPackageSignRequest) -> dict:
    if payload.sign_phrase != _SIGN_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit regulator package signing approval required')
    existing = _package_store.get(payload.ledger_id)
    if existing is not None:
        return {'state': 'telegram-regulator-package-already-signed', 'package': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    ledger = _ledger_by_id(payload.ledger_id)
    if ledger is None:
        raise HTTPException(status_code=404, detail='Telegram compliance evidence ledger not found')
    checks = {
        'ledger_exported': ledger.get('ledger_state') == 'immutable-compliance-evidence-ledger-exported',
        'ledger_hash_valid': ledger.get('ledger_hash') == _hash({'monitoring_id': ledger['monitoring_id'], 'audit_id': ledger['audit_id'], 'entries': ledger['entries'], 'checks': ledger['checks']}),
        'ledger_immutable': ledger.get('immutable') is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Regulator reporting package signing blocked', 'blockers': blockers})
    package_payload = {'ledger_id': ledger['ledger_id'], 'ledger_hash': ledger['ledger_hash'], 'regulator': payload.regulator, 'reporting_reference': payload.reporting_reference, 'checks': checks}
    package = {
        'package_id': str(uuid4()),
        **package_payload,
        'package_state': 'signed-awaiting-controlled-disclosure',
        'signature_hash': _hash(package_payload),
        'immutable': True,
        'signed_by': payload.actor,
        'signed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _package_store[payload.ledger_id] = package
    return {'state': 'telegram-regulator-reporting-package-signed', 'package': package, 'external_calls_made': 0}


@router.post('/disclosure/authorize')
def authorize_controlled_disclosure(payload: TelegramControlledDisclosureRequest) -> dict:
    if payload.disclosure_phrase != _DISCLOSE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit controlled regulator disclosure approval required')
    existing = _disclosure_store.get(payload.package_id)
    if existing is not None:
        return {'state': 'telegram-regulator-disclosure-already-authorized', 'disclosure': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    package = _package_by_id(payload.package_id)
    if package is None:
        raise HTTPException(status_code=404, detail='Telegram signed regulator package not found')
    allowed_scope = {'ledger_hash', 'entry_count', 'audit_id', 'monitoring_id', 'reattestations', 'reporting_reference'}
    invalid_scope = sorted(set(payload.scope) - allowed_scope)
    checks = {
        'package_signed': package.get('package_state') == 'signed-awaiting-controlled-disclosure',
        'package_immutable': package.get('immutable') is True,
        'signature_present': bool(package.get('signature_hash')),
        'scope_allowlisted': not invalid_scope,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Controlled regulator disclosure blocked', 'blockers': blockers, 'invalid_scope': invalid_scope})
    disclosure_payload = {'package_id': package['package_id'], 'recipient': payload.recipient, 'purpose': payload.purpose, 'scope': sorted(set(payload.scope)), 'checks': checks}
    disclosure = {
        'disclosure_id': str(uuid4()),
        **disclosure_payload,
        'disclosure_state': 'authorized-no-transport-executed',
        'authorization_hash': _hash(disclosure_payload),
        'immutable': True,
        'authorized_by': payload.actor,
        'authorized_at': datetime.now(timezone.utc).isoformat(),
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
    }
    package['package_state'] = 'controlled-disclosure-authorized'
    _disclosure_store[payload.package_id] = disclosure
    return {'state': 'telegram-controlled-regulator-disclosure-authorized', 'disclosure': disclosure, 'external_calls_made': 0, 'next_layer': 'regulator-disclosure-delivery-receipt-governance'}


@router.get('/status')
def compliance_ledger_disclosure_status() -> dict:
    return {
        'ledgers': len(_ledger_store),
        'signed_packages': len(_package_store),
        'authorized_disclosures': len(_disclosure_store),
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'mode': 'immutable-ledger-signed-reporting-package-controlled-disclosure-authorization',
    }


@router.get('/ledgers')
def list_ledgers() -> dict:
    return {'count': len(_ledger_store), 'items': list(_ledger_store.values()), 'external_calls_made': 0}


@router.get('/packages')
def list_packages() -> dict:
    return {'count': len(_package_store), 'items': list(_package_store.values()), 'external_calls_made': 0}


@router.get('/disclosures')
def list_disclosures() -> dict:
    return {'count': len(_disclosure_store), 'items': list(_disclosure_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_long_term_compliance_monitoring_v21_340 import command_center as v21_340_command_center
    return v21_340_command_center().replace('v21.340', 'v21.341').replace(
        'AURON TELEGRAM LONG TERM COMPLIANCE MONITORING COMMAND CENTER',
        'AURON TELEGRAM COMPLIANCE LEDGER DISCLOSURE COMMAND CENTER',
    )
