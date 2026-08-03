from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_certificate_renewal_governance_v21_334 import (
    _renewal_policy_store,
    _renewal_schedule_store,
)
from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_post_recertification_governance_v21_333 import _lineage
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import (
    _baseline_metrics,
    _certificate_store,
)

router = APIRouter(prefix='/auron/demo1/v21.335', tags=['auron-demo1-telegram-controlled-certificate-renewal-execution'])

_renewal_execution_store: dict[str, dict] = {}
_handover_store: dict[str, dict] = {}
_EXECUTE_PHRASE = 'EXECUTE AURON TELEGRAM CERTIFICATE RENEWAL'
_COMMIT_PHRASE = 'COMMIT AURON TELEGRAM CERTIFICATE HANDOVER'


class TelegramCertificateRenewalExecuteRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certificate_id: str = Field(min_length=1, max_length=160)
    execution_phrase: str = Field(min_length=1, max_length=280)
    minimum_reliability_score: float | None = Field(default=None, ge=0.0, le=100.0)


class TelegramCertificateHandoverCommitRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    renewal_execution_id: str = Field(min_length=1, max_length=160)
    commit_phrase: str = Field(min_length=1, max_length=280)


def reset_telegram_controlled_certificate_renewal_execution_store() -> None:
    _renewal_execution_store.clear()
    _handover_store.clear()


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _execution_by_id(execution_id: str) -> dict | None:
    return next((item for item in _renewal_execution_store.values() if item.get('renewal_execution_id') == execution_id), None)


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _execution_checks(certificate: dict, policy: dict, schedule: dict, metrics: dict) -> dict:
    chat_id = certificate['telegram_chat_id']
    lineage = _lineage(certificate)
    go_live = _go_live_store.get(chat_id)
    return {
        'certificate_currently_certified': certificate.get('certificate_state') == 'certified',
        'renewal_policy_active': policy.get('policy_state') == 'renewal-scheduled',
        'renewal_schedule_valid': schedule.get('schedule_state') == 'scheduled-awaiting-controlled-renewal-execution',
        'policy_schedule_match': schedule.get('renewal_policy_id') == policy.get('renewal_policy_id'),
        'lineage_valid': lineage['valid'],
        'lineage_depth_within_policy': lineage['depth'] <= policy['maximum_lineage_depth'],
        'reliability_threshold_met': metrics['runtime_reliability_score'] >= policy['minimum_reliability_score'],
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
    }


@router.post('/execute')
def execute_certificate_renewal(payload: TelegramCertificateRenewalExecuteRequest) -> dict:
    if payload.execution_phrase != _EXECUTE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit controlled certificate-renewal execution approval required')
    existing = _renewal_execution_store.get(payload.certificate_id)
    if existing is not None:
        return {'state': 'telegram-certificate-renewal-execution-already-created', 'execution': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    certificate = _certificate_by_id(payload.certificate_id)
    policy = _renewal_policy_store.get(payload.certificate_id)
    schedule = _renewal_schedule_store.get(payload.certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail='Telegram service certificate not found')
    if policy is None or schedule is None:
        raise HTTPException(status_code=409, detail='Governed renewal policy and schedule required before execution')

    metrics = _baseline_metrics(certificate['telegram_chat_id'])
    if payload.minimum_reliability_score is not None:
        policy_threshold = policy['minimum_reliability_score']
        policy['minimum_reliability_score'] = max(policy_threshold, payload.minimum_reliability_score)
    checks = _execution_checks(certificate, policy, schedule, metrics)
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Controlled certificate renewal execution blocked', 'blockers': blockers})

    now = datetime.now(timezone.utc).isoformat()
    successor_payload = {
        'supersedes_certificate_id': certificate['certificate_id'],
        'renewal_policy_id': policy['renewal_policy_id'],
        'renewal_schedule_id': schedule['renewal_schedule_id'],
        'telegram_chat_id': certificate['telegram_chat_id'],
        'metrics': metrics,
        'checks': checks,
    }
    successor = {
        'certificate_id': str(uuid4()),
        **successor_payload,
        'slo_baseline': {
            'delivery_success_rate': metrics['delivery_success_rate'],
            'lifecycle_completion_rate': metrics['lifecycle_completion_rate'],
            'queue_completion_rate': metrics['queue_completion_rate'],
            'dead_letter_rate': metrics['dead_letter_rate'],
        },
        'runtime_reliability_score': metrics['runtime_reliability_score'],
        'certificate_state': 'issued-awaiting-zero-downtime-handover',
        'integrity_hash': _hash(successor_payload),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': now,
        'external_calls_made': 0,
    }
    execution_payload = {
        'source_certificate_id': certificate['certificate_id'],
        'successor_certificate_id': successor['certificate_id'],
        'renewal_policy_id': policy['renewal_policy_id'],
        'renewal_schedule_id': schedule['renewal_schedule_id'],
        'checks': checks,
    }
    execution = {
        'renewal_execution_id': str(uuid4()),
        **execution_payload,
        'telegram_chat_id': certificate['telegram_chat_id'],
        'execution_state': 'successor-issued-awaiting-handover-commit',
        'integrity_hash': _hash(execution_payload),
        'immutable': True,
        'executed_by': payload.actor,
        'executed_at': now,
        'external_calls_made': 0,
    }
    _certificate_store[f'renewal:{execution["renewal_execution_id"]}'] = successor
    _renewal_execution_store[payload.certificate_id] = execution
    schedule['schedule_state'] = 'executed-awaiting-zero-downtime-handover'
    policy['policy_state'] = 'successor-issued-awaiting-handover'
    return {
        'state': 'telegram-certificate-renewal-successor-issued',
        'execution': execution,
        'successor_certificate': successor,
        'source_certificate_remains_active': True,
        'external_calls_made': 0,
        'next_layer': 'zero-downtime-certificate-handover-commit',
    }


@router.post('/handover/commit')
def commit_certificate_handover(payload: TelegramCertificateHandoverCommitRequest) -> dict:
    if payload.commit_phrase != _COMMIT_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit zero-downtime certificate handover approval required')
    existing = _handover_store.get(payload.renewal_execution_id)
    if existing is not None:
        return {'state': 'telegram-certificate-handover-already-committed', 'handover': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    execution = _execution_by_id(payload.renewal_execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail='Telegram certificate renewal execution not found')
    if execution.get('execution_state') != 'successor-issued-awaiting-handover-commit':
        raise HTTPException(status_code=409, detail='Certificate renewal execution is not awaiting handover')

    source = _certificate_by_id(execution['source_certificate_id'])
    successor = _certificate_by_id(execution['successor_certificate_id'])
    if source is None or successor is None:
        raise HTTPException(status_code=409, detail='Source or successor certificate missing')
    chat_id = execution['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    metrics = _baseline_metrics(chat_id)
    checks = {
        'source_still_certified': source.get('certificate_state') == 'certified',
        'successor_awaiting_handover': successor.get('certificate_state') == 'issued-awaiting-zero-downtime-handover',
        'successor_integrity_present': bool(successor.get('integrity_hash')) and successor.get('immutable') is True,
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
        'runtime_reliability_preserved': metrics['runtime_reliability_score'] >= successor['runtime_reliability_score'],
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        execution['execution_state'] = 'handover-blocked-source-remains-active'
        execution['handover_blockers'] = blockers
        raise HTTPException(status_code=409, detail={'message': 'Zero-downtime certificate handover blocked; source remains active', 'blockers': blockers})

    now = datetime.now(timezone.utc).isoformat()
    handover_payload = {
        'renewal_execution_id': execution['renewal_execution_id'],
        'source_certificate_id': source['certificate_id'],
        'successor_certificate_id': successor['certificate_id'],
        'telegram_chat_id': chat_id,
        'checks': checks,
    }
    handover = {
        'handover_id': str(uuid4()),
        **handover_payload,
        'handover_state': 'committed-zero-downtime',
        'integrity_hash': _hash(handover_payload),
        'immutable': True,
        'committed_by': payload.actor,
        'committed_at': now,
        'external_calls_made': 0,
    }
    source.update(certificate_state='superseded-after-governed-renewal', superseded_by=successor['certificate_id'], superseded_at=now)
    successor.update(certificate_state='certified', activated_at=now, activated_by=payload.actor)
    execution.update(execution_state='completed-zero-downtime-handover', completed_at=now, handover_id=handover['handover_id'])
    _handover_store[payload.renewal_execution_id] = handover
    policy = _renewal_policy_store.get(source['certificate_id'])
    schedule = _renewal_schedule_store.get(source['certificate_id'])
    if policy is not None:
        policy['policy_state'] = 'renewal-completed'
        policy['successor_certificate_id'] = successor['certificate_id']
    if schedule is not None:
        schedule['schedule_state'] = 'completed-zero-downtime-handover'
    if go_live is not None:
        go_live.update(service_certificate_id=successor['certificate_id'], go_live_state='renewed-certified-operational-service', continuous_mode_active=True)
    return {
        'state': 'telegram-certificate-handover-committed',
        'handover': handover,
        'active_certificate': successor,
        'service_interruption_detected': False,
        'external_calls_made': 0,
        'next_layer': 'post-renewal-continuity-observation',
    }


@router.get('/status')
def controlled_certificate_renewal_status() -> dict:
    executions = list(_renewal_execution_store.values())
    return {
        'renewal_executions': len(executions),
        'awaiting_handover': sum(1 for item in executions if item.get('execution_state') == 'successor-issued-awaiting-handover-commit'),
        'handover_blocked': sum(1 for item in executions if item.get('execution_state') == 'handover-blocked-source-remains-active'),
        'completed_handovers': len(_handover_store),
        'external_calls_made': 0,
        'mode': 'controlled-successor-certificate-issuance-zero-downtime-handover',
    }


@router.get('/executions')
def list_renewal_executions() -> dict:
    return {'count': len(_renewal_execution_store), 'items': list(_renewal_execution_store.values()), 'external_calls_made': 0}


@router.get('/handovers')
def list_certificate_handovers() -> dict:
    return {'count': len(_handover_store), 'items': list(_handover_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_certificate_renewal_governance_v21_334 import command_center as v21_334_command_center
    return v21_334_command_center().replace('v21.334', 'v21.335').replace(
        'AURON TELEGRAM CERTIFICATE RENEWAL GOVERNANCE COMMAND CENTER',
        'AURON TELEGRAM CONTROLLED CERTIFICATE RENEWAL EXECUTION COMMAND CENTER',
    )
