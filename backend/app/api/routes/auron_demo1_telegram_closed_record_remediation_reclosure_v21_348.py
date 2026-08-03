from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_closed_record_integrity_v21_347 import (
    _audit_store,
    _record_store,
    _reopen_store,
)

router = APIRouter(prefix='/auron/demo1/v21.348', tags=['auron-demo1-telegram-closed-record-remediation-reclosure'])

_remediation_store: dict[str, dict] = {}
_supersession_store: dict[str, dict] = {}
_reclosure_store: dict[str, dict] = {}
_PLAN_PHRASE = 'PLAN AURON TELEGRAM CLOSED RECORD REMEDIATION'
_SUPERSEDE_PHRASE = 'SUPERSEDE AURON TELEGRAM CLOSED RECORD EVIDENCE'
_RECLOSE_PHRASE = 'RECLOSE AURON TELEGRAM DISCLOSURE LIFECYCLE'


class ClosedRecordRemediationPlanRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    plan_phrase: str = Field(min_length=1, max_length=320)
    root_cause: str = Field(min_length=1, max_length=1800)
    corrective_action: str = Field(min_length=1, max_length=1800)
    validation_criteria: str = Field(min_length=1, max_length=1800)


class CorrectiveEvidenceSupersessionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    supersession_phrase: str = Field(min_length=1, max_length=320)
    evidence_reference: str = Field(min_length=1, max_length=300)
    evidence_statement: str = Field(min_length=1, max_length=1800)
    corrected_evidence_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')


class GovernedLifecycleReclosureRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=160)
    reclosure_phrase: str = Field(min_length=1, max_length=320)
    reclosure_reference: str = Field(min_length=1, max_length=300)
    residual_risk: str = Field(pattern='^(none|low|medium|high|critical)$')
    decision_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_closed_record_remediation_reclosure_store() -> None:
    _remediation_store.clear()
    _supersession_store.clear()
    _reclosure_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _record_by_id(record_id: str) -> dict | None:
    return next((item for item in _record_store.values() if item.get('record_id') == record_id), None)


def _latest_audit(record_id: str) -> dict | None:
    audits = _audit_store.get(record_id, [])
    return audits[-1] if audits else None


@router.post('/remediation/plan')
def plan_closed_record_remediation(payload: ClosedRecordRemediationPlanRequest) -> dict:
    if payload.plan_phrase != _PLAN_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit closed-record remediation planning approval required')
    existing = _remediation_store.get(payload.record_id)
    if existing is not None:
        return {'state': 'telegram-closed-record-remediation-already-planned', 'remediation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    record = _record_by_id(payload.record_id)
    reopen = _reopen_store.get(payload.record_id)
    latest = _latest_audit(payload.record_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram closed-disclosure record not found')
    checks = {
        'case_reopened': bool(reopen and reopen.get('reopen_state') == 'compliance-case-reopened'),
        'trigger_audit_detected_drift': bool(latest and latest.get('audit_state') == 'integrity-drift-detected'),
        'record_reopened': record.get('record_state') == 'compliance-case-reopened',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Closed-record remediation planning blocked', 'blockers': blockers})
    data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'reopen_id': reopen['reopen_id'],
        'trigger_audit_id': latest['audit_id'],
        'root_cause': payload.root_cause,
        'corrective_action': payload.corrective_action,
        'validation_criteria': payload.validation_criteria,
        'checks': checks,
    }
    remediation = {
        'remediation_id': str(uuid4()),
        **data,
        'remediation_state': 'corrective-evidence-required',
        'integrity_hash': _hash(data),
        'immutable': True,
        'planned_by': payload.actor,
        'planned_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _remediation_store[payload.record_id] = remediation
    record['record_state'] = 'closed-record-remediation-active'
    return {'state': 'telegram-closed-record-remediation-planned', 'remediation': remediation, 'record': record, 'external_calls_made': 0}


@router.post('/evidence/supersede')
def supersede_closed_record_evidence(payload: CorrectiveEvidenceSupersessionRequest) -> dict:
    if payload.supersession_phrase != _SUPERSEDE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit corrective evidence supersession approval required')
    existing = _supersession_store.get(payload.record_id)
    if existing is not None:
        return {'state': 'telegram-corrective-evidence-already-superseded', 'supersession': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    record = _record_by_id(payload.record_id)
    remediation = _remediation_store.get(payload.record_id)
    if record is None or remediation is None:
        raise HTTPException(status_code=409, detail='Approved remediation plan required before evidence supersession')
    checks = {
        'remediation_active': remediation.get('remediation_state') == 'corrective-evidence-required',
        'remediation_immutable': remediation.get('immutable') is True and bool(remediation.get('integrity_hash')),
        'record_in_remediation': record.get('record_state') == 'closed-record-remediation-active',
        'corrected_hash_differs_from_baseline': payload.corrected_evidence_hash != record.get('baseline_evidence_hash'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Corrective evidence supersession blocked', 'blockers': blockers})
    data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'remediation_id': remediation['remediation_id'],
        'superseded_baseline_evidence_hash': record['baseline_evidence_hash'],
        'corrected_evidence_hash': payload.corrected_evidence_hash,
        'evidence_reference': payload.evidence_reference,
        'evidence_statement': payload.evidence_statement,
        'checks': checks,
    }
    supersession = {
        'supersession_id': str(uuid4()),
        **data,
        'supersession_state': 'corrective-evidence-superseded-awaiting-reclosure',
        'integrity_hash': _hash(data),
        'immutable': True,
        'superseded_by': payload.actor,
        'superseded_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _supersession_store[payload.record_id] = supersession
    remediation['remediation_state'] = 'corrective-evidence-validated-awaiting-reclosure'
    record.update(
        record_state='corrective-evidence-awaiting-reclosure',
        superseded_baseline_evidence_hash=record['baseline_evidence_hash'],
        baseline_evidence_hash=payload.corrected_evidence_hash,
        corrective_supersession_id=supersession['supersession_id'],
    )
    return {'state': 'telegram-closed-record-corrective-evidence-superseded', 'supersession': supersession, 'record': record, 'external_calls_made': 0}


@router.post('/lifecycle/reclose')
def reclose_disclosure_lifecycle(payload: GovernedLifecycleReclosureRequest) -> dict:
    if payload.reclosure_phrase != _RECLOSE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit governed disclosure lifecycle reclosure approval required')
    existing = _reclosure_store.get(payload.record_id)
    if existing is not None:
        return {'state': 'telegram-disclosure-lifecycle-already-reclosed', 'reclosure': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    record = _record_by_id(payload.record_id)
    remediation = _remediation_store.get(payload.record_id)
    supersession = _supersession_store.get(payload.record_id)
    reopen = _reopen_store.get(payload.record_id)
    if record is None or remediation is None or supersession is None or reopen is None:
        raise HTTPException(status_code=409, detail='Completed remediation, supersession and reopened-case evidence required')
    checks = {
        'corrective_evidence_validated': remediation.get('remediation_state') == 'corrective-evidence-validated-awaiting-reclosure',
        'supersession_immutable': supersession.get('immutable') is True and bool(supersession.get('integrity_hash')),
        'corrected_hash_matches_record': supersession.get('corrected_evidence_hash') == record.get('baseline_evidence_hash'),
        'case_still_reopened': reopen.get('reopen_state') == 'compliance-case-reopened',
        'residual_risk_acceptable': payload.residual_risk in {'none', 'low'},
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Governed lifecycle reclosure blocked', 'blockers': blockers})
    data = {
        'record_id': record['record_id'],
        'archive_id': record['archive_id'],
        'reopen_id': reopen['reopen_id'],
        'remediation_id': remediation['remediation_id'],
        'supersession_id': supersession['supersession_id'],
        'corrected_evidence_hash': supersession['corrected_evidence_hash'],
        'residual_risk': payload.residual_risk,
        'reclosure_reference': payload.reclosure_reference,
        'decision_statement': payload.decision_statement,
        'checks': checks,
    }
    reclosure = {
        'reclosure_id': str(uuid4()),
        **data,
        'reclosure_state': 'governed-disclosure-lifecycle-reclosed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'reclosed_by': payload.actor,
        'reclosed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _reclosure_store[payload.record_id] = reclosure
    reopen.update(reopen_state='remediated-compliance-case-reclosed', reclosure_id=reclosure['reclosure_id'], reclosed_at=reclosure['reclosed_at'])
    remediation['remediation_state'] = 'remediation-completed-reclosed'
    record.update(record_state='retained-closed-disclosure-record', last_reclosure_id=reclosure['reclosure_id'])
    return {'state': 'telegram-disclosure-lifecycle-governed-reclosure-completed', 'reclosure': reclosure, 'record': record, 'external_calls_made': 0, 'next_layer': 'post-remediation-probation-and-reclosure-certification'}


@router.get('/status')
def closed_record_remediation_status() -> dict:
    return {
        'remediation_plans': len(_remediation_store),
        'evidence_supersessions': len(_supersession_store),
        'governed_reclosures': len(_reclosure_store),
        'active_remediations': sum(1 for item in _remediation_store.values() if item.get('remediation_state') != 'remediation-completed-reclosed'),
        'external_calls_made': 0,
        'mode': 'closed-record-remediation-corrective-evidence-supersession-governed-reclosure',
    }


@router.get('/remediations')
def list_remediations() -> dict:
    return {'count': len(_remediation_store), 'items': list(_remediation_store.values()), 'external_calls_made': 0}


@router.get('/supersessions')
def list_supersessions() -> dict:
    return {'count': len(_supersession_store), 'items': list(_supersession_store.values()), 'external_calls_made': 0}


@router.get('/reclosures')
def list_reclosures() -> dict:
    return {'count': len(_reclosure_store), 'items': list(_reclosure_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_closed_record_integrity_v21_347 import command_center as v21_347_command_center
    return v21_347_command_center().replace('v21.347', 'v21.348').replace(
        'AURON TELEGRAM CLOSED RECORD INTEGRITY COMMAND CENTER',
        'AURON TELEGRAM CLOSED RECORD REMEDIATION RECLOSURE COMMAND CENTER',
    )
