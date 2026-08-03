from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_analytics_health_supervisor_v21_327 import _health_snapshot_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_runtime_health_remediation_v21_328 import _remediation_store

router = APIRouter(prefix='/auron/demo1/v21.329', tags=['auron-demo1-telegram-restoration-probation'])

_probation_store: dict[str, dict] = {}
_START_PHRASE = 'START AURON TELEGRAM RESTORATION PROBATION'
_COMPLETE_PHRASE = 'COMPLETE AURON TELEGRAM RESTORATION PROBATION'


class TelegramRestorationProbationStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    anomaly_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=220)
    observation_window_minutes: int = Field(default=30, ge=1, le=1440)
    required_healthy_observations: int = Field(default=3, ge=1, le=100)
    rollback_on_degraded: bool = False


class TelegramRestorationProbationObserveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    probation_id: str = Field(min_length=1, max_length=160)
    observed_at: datetime | None = None


class TelegramRestorationProbationCompleteRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    probation_id: str = Field(min_length=1, max_length=160)
    completion_phrase: str = Field(min_length=1, max_length=220)


def reset_telegram_restoration_probation_store() -> None:
    _probation_store.clear()


def _probation_by_id(probation_id: str) -> dict | None:
    return next((item for item in _probation_store.values() if item.get('probation_id') == probation_id), None)


def _rollback(record: dict, actor: str, reason: str, now: str) -> None:
    chat_id = record['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    if go_live is not None:
        go_live.update(
            continuous_mode_active=False,
            go_live_state='rolled-back-during-restoration-probation',
            paused_at=now,
            pause_reason=reason,
        )
    circuit = _circuit_store.setdefault(chat_id, {'telegram_chat_id': chat_id})
    circuit.update(state='open', opened_at=now, opened_reason=reason)
    record.update(
        probation_state='rolled-back',
        rollback_reason=reason,
        rolled_back_by=actor,
        rolled_back_at=now,
        completed_at=now,
    )


@router.post('/start')
def start_restoration_probation(payload: TelegramRestorationProbationStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit restoration-probation start approval required')
    existing = _probation_store.get(payload.anomaly_id)
    if existing is not None:
        return {'state': 'telegram-restoration-probation-already-started', 'probation': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    remediation = _remediation_store.get(payload.anomaly_id)
    if remediation is None or remediation.get('remediation_state') != 'restored':
        raise HTTPException(status_code=409, detail='Completed v21.328 service restoration required before probation')
    chat_id = remediation['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    if go_live is None or not go_live.get('continuous_mode_active'):
        raise HTTPException(status_code=409, detail='Restored Telegram continuous service must be active')
    now_dt = datetime.now(timezone.utc)
    record = {
        'probation_id': str(uuid4()),
        'anomaly_id': payload.anomaly_id,
        'remediation_id': remediation['remediation_id'],
        'telegram_chat_id': chat_id,
        'observation_window_minutes': payload.observation_window_minutes,
        'required_healthy_observations': payload.required_healthy_observations,
        'rollback_on_degraded': payload.rollback_on_degraded,
        'healthy_observations': 0,
        'degraded_observations': 0,
        'critical_observations': 0,
        'observation_history': [],
        'probation_state': 'active-observation-window',
        'started_by': payload.actor,
        'started_at': now_dt.isoformat(),
        'window_ends_at': (now_dt + timedelta(minutes=payload.observation_window_minutes)).isoformat(),
        'completed_at': None,
        'external_calls_made': 0,
    }
    _probation_store[payload.anomaly_id] = record
    go_live['go_live_state'] = 'restoration-probation-active'
    return {'state': 'telegram-restoration-probation-started', 'probation': record, 'external_calls_made': 0}


@router.post('/observe')
def observe_restoration_probation(payload: TelegramRestorationProbationObserveRequest) -> dict:
    record = _probation_by_id(payload.probation_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram restoration probation not found')
    if record.get('probation_state') != 'active-observation-window':
        return {'state': 'telegram-restoration-probation-already-terminal', 'probation': record, 'idempotent_replay': True, 'external_calls_made': 0}
    snapshot = _health_snapshot_store.get(record['telegram_chat_id'])
    if snapshot is None:
        raise HTTPException(status_code=409, detail='Runtime-health snapshot required for probation observation')
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    observed_at_iso = observed_at.isoformat()
    state = snapshot.get('health_state')
    if state not in {'healthy', 'degraded', 'critical'}:
        raise HTTPException(status_code=409, detail='Unsupported runtime-health state for probation')
    observation = {
        'observation_id': str(uuid4()),
        'health_snapshot_id': snapshot.get('health_snapshot_id'),
        'health_state': state,
        'observed_by': payload.actor,
        'observed_at': observed_at_iso,
    }
    record['observation_history'].append(observation)
    record[f'{state}_observations'] += 1
    if state == 'critical' or (state == 'degraded' and record.get('rollback_on_degraded')):
        _rollback(record, payload.actor, f'probation-{state}-health-observation', observed_at_iso)
        return {'state': 'telegram-restoration-probation-rolled-back', 'probation': record, 'external_calls_made': 0}
    return {
        'state': 'telegram-restoration-probation-observation-recorded',
        'probation': record,
        'eligible_for_completion': record['healthy_observations'] >= record['required_healthy_observations'],
        'external_calls_made': 0,
    }


@router.post('/complete')
def complete_restoration_probation(payload: TelegramRestorationProbationCompleteRequest) -> dict:
    if payload.completion_phrase != _COMPLETE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit restoration-probation completion approval required')
    record = _probation_by_id(payload.probation_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Telegram restoration probation not found')
    if record.get('probation_state') == 'completed-stable':
        return {'state': 'telegram-restoration-probation-already-completed', 'probation': record, 'idempotent_replay': True, 'external_calls_made': 0}
    if record.get('probation_state') != 'active-observation-window':
        raise HTTPException(status_code=409, detail='Rolled-back probation cannot be completed')
    checks = {
        'healthy_observation_threshold_met': record['healthy_observations'] >= record['required_healthy_observations'],
        'no_critical_observations': record['critical_observations'] == 0,
        'service_still_active': bool(_go_live_store.get(record['telegram_chat_id'], {}).get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(record['telegram_chat_id'], {}).get('state', 'closed') == 'closed',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram restoration probation completion blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    record.update(
        probation_state='completed-stable',
        completion_checks=checks,
        completed_by=payload.actor,
        completed_at=now,
    )
    go_live = _go_live_store.get(record['telegram_chat_id'])
    if go_live is not None:
        go_live['go_live_state'] = 'operational-after-successful-restoration-probation'
    return {'state': 'telegram-restoration-probation-completed', 'probation': record, 'external_calls_made': 0}


@router.get('/status')
def probation_status() -> dict:
    items = list(_probation_store.values())
    return {
        'probations': len(items),
        'active': sum(1 for item in items if item.get('probation_state') == 'active-observation-window'),
        'completed': sum(1 for item in items if item.get('probation_state') == 'completed-stable'),
        'rolled_back': sum(1 for item in items if item.get('probation_state') == 'rolled-back'),
        'external_calls_made': 0,
        'mode': 'post-restoration-observation-with-automatic-rollback',
    }


@router.get('/probations')
def list_probations() -> dict:
    items = sorted(_probation_store.values(), key=lambda item: item['started_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_runtime_health_remediation_v21_328 import command_center as v21_328_command_center
    return v21_328_command_center().replace('v21.328', 'v21.329').replace(
        'AURON TELEGRAM RUNTIME HEALTH REMEDIATION COMMAND CENTER',
        'AURON TELEGRAM RESTORATION PROBATION COMMAND CENTER',
    )
