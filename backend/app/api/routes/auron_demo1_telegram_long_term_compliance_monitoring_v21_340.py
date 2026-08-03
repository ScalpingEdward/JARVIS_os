from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_erasure_audit_compliance_closure_v21_339 import (
    _attestation_store,
    _audit_store,
    _closure_store,
)
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _certificate_store

router = APIRouter(prefix='/auron/demo1/v21.340', tags=['auron-demo1-telegram-long-term-compliance-monitoring'])

_monitoring_store: dict[str, dict] = {}
_reattestation_store: dict[str, dict] = {}
_exception_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM LONG TERM COMPLIANCE MONITORING'
_REATTEST_PHRASE = 'REATTEST AURON TELEGRAM COMPLIANCE EVIDENCE'
_EXCEPTION_PHRASE = 'OPEN AURON TELEGRAM REGULATORY EXCEPTION'
_RESOLVE_PHRASE = 'RESOLVE AURON TELEGRAM REGULATORY EXCEPTION'


class TelegramComplianceMonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    audit_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    reattestation_interval_days: int = Field(default=90, ge=1, le=3650)


class TelegramComplianceMonitoringEvaluateRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    evaluated_at: datetime | None = None


class TelegramComplianceReattestRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    reattestation_phrase: str = Field(min_length=1, max_length=320)


class TelegramRegulatoryExceptionOpenRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    exception_phrase: str = Field(min_length=1, max_length=320)
    authority: str = Field(min_length=1, max_length=300)
    reference_id: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=1500)


class TelegramRegulatoryExceptionResolveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    resolve_phrase: str = Field(min_length=1, max_length=320)
    resolution: str = Field(min_length=1, max_length=1500)


def reset_telegram_long_term_compliance_monitoring_store() -> None:
    _monitoring_store.clear()
    _reattestation_store.clear()
    _exception_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _audit_by_id(audit_id: str) -> dict | None:
    return next((item for item in _audit_store.values() if item.get('audit_id') == audit_id), None)


def _monitoring_by_id(monitoring_id: str) -> dict | None:
    return next((item for item in _monitoring_store.values() if item.get('monitoring_id') == monitoring_id), None)


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


@router.post('/start')
def start_long_term_monitoring(payload: TelegramComplianceMonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit long-term compliance monitoring approval required')
    existing = _monitoring_store.get(payload.audit_id)
    if existing is not None:
        return {'state': 'telegram-compliance-monitoring-already-started', 'monitoring': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    audit = _audit_by_id(payload.audit_id)
    closure = _closure_store.get(payload.audit_id)
    attestation = _attestation_store.get(payload.audit_id)
    if audit is None or closure is None or attestation is None:
        raise HTTPException(status_code=404, detail='Completed v21.339 compliance evidence not found')
    successor = _certificate_by_id(audit['successor_certificate_id'])
    go_live = next((item for item in _go_live_store.values() if item.get('service_certificate_id') == audit['successor_certificate_id']), None)
    checks = {
        'audit_closed': audit.get('audit_state') == 'completed-compliance-closure',
        'closure_valid': closure.get('closure_state') == 'erasure-compliance-case-closed',
        'closure_immutable': closure.get('immutable') is True and bool(closure.get('integrity_hash')),
        'attestation_valid': attestation.get('attestation_state') == 'independently-attested-valid-erasure-chain',
        'successor_preserved': bool(successor and successor.get('certificate_state') == 'certified'),
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Long-term compliance monitoring blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc)
    evidence = {
        'audit_id': audit['audit_id'],
        'closure_id': closure['closure_id'],
        'attestation_id': attestation['attestation_id'],
        'evidence_chain_hash': audit['evidence_chain_hash'],
        'closure_integrity_hash': closure['integrity_hash'],
        'attestation_integrity_hash': attestation['integrity_hash'],
        'successor_certificate_id': audit['successor_certificate_id'],
    }
    record = {
        'monitoring_id': str(uuid4()),
        **evidence,
        'monitoring_state': 'active-compliance-monitoring',
        'baseline_evidence_hash': _hash(evidence),
        'reattestation_interval_days': payload.reattestation_interval_days,
        'next_reattestation_due_at': (now + timedelta(days=payload.reattestation_interval_days)).isoformat(),
        'last_reattested_at': now.isoformat(),
        'evaluation_count': 0,
        'reattestation_count': 0,
        'immutable': True,
        'started_by': payload.actor,
        'started_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _monitoring_store[payload.audit_id] = record
    return {'state': 'telegram-long-term-compliance-monitoring-started', 'monitoring': record, 'external_calls_made': 0}


@router.post('/evaluate')
def evaluate_compliance_monitoring(payload: TelegramComplianceMonitoringEvaluateRequest) -> dict:
    record = _monitoring_by_id(payload.monitoring_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram compliance monitoring record not found')
    audit = _audit_by_id(record['audit_id'])
    closure = _closure_store.get(record['audit_id'])
    attestation = _attestation_store.get(record['audit_id'])
    successor = _certificate_by_id(record['successor_certificate_id'])
    go_live = next((item for item in _go_live_store.values() if item.get('service_certificate_id') == record['successor_certificate_id']), None)
    evaluated_at = payload.evaluated_at or datetime.now(timezone.utc)
    due_at = datetime.fromisoformat(record['next_reattestation_due_at'])
    evidence = {
        'audit_id': record['audit_id'],
        'closure_id': record['closure_id'],
        'attestation_id': record['attestation_id'],
        'evidence_chain_hash': audit.get('evidence_chain_hash') if audit else None,
        'closure_integrity_hash': closure.get('integrity_hash') if closure else None,
        'attestation_integrity_hash': attestation.get('integrity_hash') if attestation else None,
        'successor_certificate_id': record['successor_certificate_id'],
    }
    checks = {
        'evidence_chain_unchanged': _hash(evidence) == record['baseline_evidence_hash'],
        'closure_still_valid': bool(closure and closure.get('closure_state') == 'erasure-compliance-case-closed'),
        'attestation_still_valid': bool(attestation and attestation.get('attestation_state') == 'independently-attested-valid-erasure-chain'),
        'successor_preserved': bool(successor and successor.get('certificate_state') == 'certified'),
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
    }
    exception = _exception_store.get(record['monitoring_id'])
    exception_active = bool(exception and exception.get('exception_state') == 'open-regulatory-exception')
    due = evaluated_at >= due_at
    if not all(checks.values()):
        state = 'compliance-evidence-drift-exception-required'
    elif exception_active:
        state = 'regulatory-exception-active'
    elif due:
        state = 'periodic-reattestation-due'
    else:
        state = 'active-compliance-monitoring'
    record.update(monitoring_state=state, evaluation_count=record['evaluation_count'] + 1, last_evaluated_at=evaluated_at.isoformat(), latest_checks=checks)
    return {'state': f'telegram-{state}', 'monitoring': record, 'checks': checks, 'reattestation_due': due, 'regulatory_exception_active': exception_active, 'external_calls_made': 0}


@router.post('/reattest')
def reattest_compliance_evidence(payload: TelegramComplianceReattestRequest) -> dict:
    if payload.reattestation_phrase != _REATTEST_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit compliance evidence re-attestation required')
    record = _monitoring_by_id(payload.monitoring_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram compliance monitoring record not found')
    if record.get('monitoring_state') not in {'periodic-reattestation-due', 'active-compliance-monitoring'}:
        raise HTTPException(status_code=409, detail='Compliance evidence cannot be re-attested in current state')
    checks = record.get('latest_checks') or {}
    if checks and not all(checks.values()):
        raise HTTPException(status_code=409, detail='Changed compliance evidence cannot be re-attested')
    now = datetime.now(timezone.utc)
    payload_record = {'monitoring_id': record['monitoring_id'], 'audit_id': record['audit_id'], 'baseline_evidence_hash': record['baseline_evidence_hash'], 'sequence': record['reattestation_count'] + 1}
    attestation = {
        'reattestation_id': str(uuid4()),
        **payload_record,
        'reattestation_state': 'periodic-compliance-evidence-reattested',
        'integrity_hash': _hash(payload_record),
        'immutable': True,
        'reattested_by': payload.actor,
        'reattested_at': now.isoformat(),
        'external_calls_made': 0,
    }
    _reattestation_store.setdefault(record['monitoring_id'], []).append(attestation)
    record.update(monitoring_state='active-compliance-monitoring', reattestation_count=record['reattestation_count'] + 1, last_reattested_at=now.isoformat(), next_reattestation_due_at=(now + timedelta(days=record['reattestation_interval_days'])).isoformat())
    return {'state': 'telegram-compliance-evidence-reattested', 'reattestation': attestation, 'monitoring': record, 'external_calls_made': 0}


@router.post('/exception/open')
def open_regulatory_exception(payload: TelegramRegulatoryExceptionOpenRequest) -> dict:
    if payload.exception_phrase != _EXCEPTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit regulatory-exception approval required')
    record = _monitoring_by_id(payload.monitoring_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram compliance monitoring record not found')
    existing = _exception_store.get(payload.monitoring_id)
    if existing and existing.get('exception_state') == 'open-regulatory-exception':
        return {'state': 'telegram-regulatory-exception-already-open', 'exception': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    data = {'monitoring_id': record['monitoring_id'], 'authority': payload.authority, 'reference_id': payload.reference_id, 'reason': payload.reason}
    exception = {'exception_id': str(uuid4()), **data, 'exception_state': 'open-regulatory-exception', 'integrity_hash': _hash(data), 'immutable': True, 'opened_by': payload.actor, 'opened_at': datetime.now(timezone.utc).isoformat(), 'external_calls_made': 0}
    _exception_store[payload.monitoring_id] = exception
    record['monitoring_state'] = 'regulatory-exception-active'
    return {'state': 'telegram-regulatory-exception-opened', 'exception': exception, 'external_calls_made': 0}


@router.post('/exception/resolve')
def resolve_regulatory_exception(payload: TelegramRegulatoryExceptionResolveRequest) -> dict:
    if payload.resolve_phrase != _RESOLVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit regulatory-exception resolution required')
    exception = _exception_store.get(payload.monitoring_id)
    record = _monitoring_by_id(payload.monitoring_id)
    if exception is None or record is None:
        raise HTTPException(status_code=404, detail='Telegram regulatory exception not found')
    if exception.get('exception_state') == 'resolved-regulatory-exception':
        return {'state': 'telegram-regulatory-exception-already-resolved', 'exception': exception, 'idempotent_replay': True, 'external_calls_made': 0}
    now = datetime.now(timezone.utc).isoformat()
    exception.update(exception_state='resolved-regulatory-exception', resolution=payload.resolution, resolved_by=payload.actor, resolved_at=now)
    record['monitoring_state'] = 'periodic-reattestation-due'
    return {'state': 'telegram-regulatory-exception-resolved', 'exception': exception, 'monitoring': record, 'external_calls_made': 0, 'next_layer': 'compliance-evidence-ledger-export'}


@router.get('/status')
def long_term_compliance_status() -> dict:
    records = list(_monitoring_store.values())
    return {'monitoring_records': len(records), 'active': sum(1 for item in records if item.get('monitoring_state') == 'active-compliance-monitoring'), 'reattestation_due': sum(1 for item in records if item.get('monitoring_state') == 'periodic-reattestation-due'), 'exceptions_open': sum(1 for item in _exception_store.values() if item.get('exception_state') == 'open-regulatory-exception'), 'reattestations': sum(len(items) for items in _reattestation_store.values()), 'external_calls_made': 0, 'mode': 'long-term-compliance-monitoring-periodic-reattestation-regulatory-exception-governance'}


@router.get('/monitoring')
def list_monitoring() -> dict:
    return {'count': len(_monitoring_store), 'items': list(_monitoring_store.values()), 'external_calls_made': 0}


@router.get('/exceptions')
def list_exceptions() -> dict:
    return {'count': len(_exception_store), 'items': list(_exception_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_erasure_audit_compliance_closure_v21_339 import command_center as v21_339_command_center
    return v21_339_command_center().replace('v21.339', 'v21.340').replace('AURON TELEGRAM ERASURE AUDIT COMPLIANCE CLOSURE COMMAND CENTER', 'AURON TELEGRAM LONG TERM COMPLIANCE MONITORING COMMAND CENTER')
