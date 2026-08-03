from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_post_recertification_governance_v21_333 import (
    _lineage,
    _lineage_audit_store,
    _observation_store,
)
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import (
    _baseline_metrics,
    _certificate_store,
)

router = APIRouter(prefix='/auron/demo1/v21.334', tags=['auron-demo1-telegram-certificate-renewal-governance'])

_renewal_policy_store: dict[str, dict] = {}
_renewal_schedule_store: dict[str, dict] = {}
_POLICY_PHRASE = 'ESTABLISH AURON TELEGRAM CERTIFICATE RENEWAL POLICY'
_SCHEDULE_PHRASE = 'SCHEDULE AURON TELEGRAM CERTIFICATE RENEWAL'


class TelegramCertificateRenewalPolicyRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certificate_id: str = Field(min_length=1, max_length=160)
    policy_phrase: str = Field(min_length=1, max_length=280)
    certificate_lifetime_days: int = Field(default=90, ge=1, le=3650)
    renewal_lead_days: int = Field(default=14, ge=1, le=365)
    minimum_reliability_score: float = Field(default=85.0, ge=0.0, le=100.0)
    maximum_lineage_depth: int = Field(default=20, ge=1, le=1000)


class TelegramCertificateRenewalEvaluateRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certificate_id: str = Field(min_length=1, max_length=160)
    evaluated_at: datetime | None = None


class TelegramCertificateRenewalScheduleRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certificate_id: str = Field(min_length=1, max_length=160)
    schedule_phrase: str = Field(min_length=1, max_length=280)
    reason: str = Field(min_length=1, max_length=1000)


def reset_telegram_certificate_renewal_governance_store() -> None:
    _renewal_policy_store.clear()
    _renewal_schedule_store.clear()


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


def _completed_governance(certificate_id: str) -> dict | None:
    record = _observation_store.get(certificate_id)
    if record and record.get('governance_state') == 'completed-long-horizon-governance':
        return record
    return None


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@router.post('/policy')
def establish_certificate_renewal_policy(payload: TelegramCertificateRenewalPolicyRequest) -> dict:
    if payload.policy_phrase != _POLICY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate-renewal policy approval required')
    existing = _renewal_policy_store.get(payload.certificate_id)
    if existing is not None:
        return {'state': 'telegram-certificate-renewal-policy-already-established', 'policy': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    certificate = _certificate_by_id(payload.certificate_id)
    governance = _completed_governance(payload.certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail='Telegram service certificate not found')
    if governance is None:
        raise HTTPException(status_code=409, detail='Completed v21.333 governance required before renewal policy')
    if payload.renewal_lead_days >= payload.certificate_lifetime_days:
        raise HTTPException(status_code=409, detail='Renewal lead time must be shorter than certificate lifetime')
    lineage = _lineage(certificate)
    checks = {
        'certificate_certified': certificate.get('certificate_state') == 'certified',
        'lineage_valid': lineage['valid'],
        'lineage_depth_within_policy': lineage['depth'] <= payload.maximum_lineage_depth,
        'lineage_audit_present': governance.get('lineage_audit_id') in {item.get('lineage_audit_id') for item in _lineage_audit_store.values()},
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Certificate renewal policy blocked', 'blockers': blockers})
    certified_at = _parse_datetime(certificate.get('certified_at')) or datetime.now(timezone.utc)
    expires_at = certified_at + timedelta(days=payload.certificate_lifetime_days)
    renewal_window_opens_at = expires_at - timedelta(days=payload.renewal_lead_days)
    policy_payload = {
        'certificate_id': payload.certificate_id,
        'telegram_chat_id': certificate['telegram_chat_id'],
        'certificate_lifetime_days': payload.certificate_lifetime_days,
        'renewal_lead_days': payload.renewal_lead_days,
        'minimum_reliability_score': payload.minimum_reliability_score,
        'maximum_lineage_depth': payload.maximum_lineage_depth,
        'certified_at': certified_at.isoformat(),
        'renewal_window_opens_at': renewal_window_opens_at.isoformat(),
        'expires_at': expires_at.isoformat(),
        'checks': checks,
    }
    now = datetime.now(timezone.utc).isoformat()
    policy = {
        'renewal_policy_id': str(uuid4()),
        **policy_payload,
        'policy_state': 'active-awaiting-renewal-window',
        'integrity_hash': _hash(policy_payload),
        'immutable': True,
        'established_by': payload.actor,
        'established_at': now,
        'external_calls_made': 0,
    }
    _renewal_policy_store[payload.certificate_id] = policy
    return {'state': 'telegram-certificate-renewal-policy-established', 'policy': policy, 'external_calls_made': 0}


@router.post('/evaluate')
def evaluate_certificate_renewal(payload: TelegramCertificateRenewalEvaluateRequest) -> dict:
    policy = _renewal_policy_store.get(payload.certificate_id)
    certificate = _certificate_by_id(payload.certificate_id)
    if policy is None or certificate is None:
        raise HTTPException(status_code=404, detail='Telegram certificate renewal policy not found')
    evaluated_at = payload.evaluated_at or datetime.now(timezone.utc)
    opens_at = _parse_datetime(policy['renewal_window_opens_at'])
    expires_at = _parse_datetime(policy['expires_at'])
    current = _baseline_metrics(certificate['telegram_chat_id'])
    lineage = _lineage(certificate)
    go_live = _go_live_store.get(certificate['telegram_chat_id'])
    circuit_closed = _circuit_store.get(certificate['telegram_chat_id'], {}).get('state', 'closed') == 'closed'
    due = bool(opens_at and evaluated_at >= opens_at)
    expired = bool(expires_at and evaluated_at >= expires_at)
    checks = {
        'lineage_valid': lineage['valid'],
        'lineage_depth_within_policy': lineage['depth'] <= policy['maximum_lineage_depth'],
        'reliability_threshold_met': current['runtime_reliability_score'] >= policy['minimum_reliability_score'],
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': circuit_closed,
        'certificate_not_expired': not expired,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    renewal_state = 'expired' if expired else ('renewal-due' if due else 'not-due')
    if blockers and renewal_state != 'expired':
        renewal_state = 'governance-review-required'
    evaluation = {
        'certificate_id': payload.certificate_id,
        'telegram_chat_id': certificate['telegram_chat_id'],
        'renewal_state': renewal_state,
        'renewal_due': due,
        'expired': expired,
        'metrics': current,
        'lineage': lineage,
        'checks': checks,
        'blockers': blockers,
        'evaluated_by': payload.actor,
        'evaluated_at': evaluated_at.isoformat(),
        'external_calls_made': 0,
    }
    policy['latest_evaluation'] = evaluation
    policy['policy_state'] = renewal_state
    return {'state': f'telegram-certificate-{renewal_state}', 'evaluation': evaluation, 'external_calls_made': 0}


@router.post('/schedule')
def schedule_certificate_renewal(payload: TelegramCertificateRenewalScheduleRequest) -> dict:
    if payload.schedule_phrase != _SCHEDULE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit certificate-renewal scheduling approval required')
    existing = _renewal_schedule_store.get(payload.certificate_id)
    if existing is not None:
        return {'state': 'telegram-certificate-renewal-already-scheduled', 'schedule': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    policy = _renewal_policy_store.get(payload.certificate_id)
    if policy is None:
        raise HTTPException(status_code=404, detail='Telegram certificate renewal policy not found')
    evaluation = policy.get('latest_evaluation')
    if evaluation is None or evaluation.get('renewal_state') != 'renewal-due':
        raise HTTPException(status_code=409, detail='Certificate renewal can only be scheduled inside a valid renewal window')
    if evaluation.get('blockers'):
        raise HTTPException(status_code=409, detail={'message': 'Certificate renewal scheduling blocked', 'blockers': evaluation['blockers']})
    now = datetime.now(timezone.utc).isoformat()
    schedule_payload = {
        'certificate_id': payload.certificate_id,
        'telegram_chat_id': evaluation['telegram_chat_id'],
        'renewal_policy_id': policy['renewal_policy_id'],
        'renewal_window_opens_at': policy['renewal_window_opens_at'],
        'expires_at': policy['expires_at'],
        'reason': payload.reason,
    }
    schedule = {
        'renewal_schedule_id': str(uuid4()),
        **schedule_payload,
        'schedule_state': 'scheduled-awaiting-controlled-renewal-execution',
        'integrity_hash': _hash(schedule_payload),
        'immutable': True,
        'scheduled_by': payload.actor,
        'scheduled_at': now,
        'external_calls_made': 0,
    }
    _renewal_schedule_store[payload.certificate_id] = schedule
    policy['policy_state'] = 'renewal-scheduled'
    return {'state': 'telegram-certificate-renewal-scheduled', 'schedule': schedule, 'external_calls_made': 0, 'next_layer': 'controlled-certificate-renewal-execution'}


@router.get('/status')
def certificate_renewal_governance_status() -> dict:
    policies = list(_renewal_policy_store.values())
    return {
        'renewal_policies': len(policies),
        'not_due': sum(1 for item in policies if item.get('policy_state') == 'not-due'),
        'renewal_due': sum(1 for item in policies if item.get('policy_state') == 'renewal-due'),
        'review_required': sum(1 for item in policies if item.get('policy_state') == 'governance-review-required'),
        'renewal_scheduled': len(_renewal_schedule_store),
        'external_calls_made': 0,
        'mode': 'certificate-aging-policy-long-horizon-reliability-governed-renewal-scheduling',
    }


@router.get('/policies')
def list_renewal_policies() -> dict:
    return {'count': len(_renewal_policy_store), 'items': list(_renewal_policy_store.values()), 'external_calls_made': 0}


@router.get('/schedules')
def list_renewal_schedules() -> dict:
    return {'count': len(_renewal_schedule_store), 'items': list(_renewal_schedule_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_post_recertification_governance_v21_333 import command_center as v21_333_command_center
    return v21_333_command_center().replace('v21.333', 'v21.334').replace(
        'AURON TELEGRAM POST RECERTIFICATION GOVERNANCE COMMAND CENTER',
        'AURON TELEGRAM CERTIFICATE RENEWAL GOVERNANCE COMMAND CENTER',
    )
