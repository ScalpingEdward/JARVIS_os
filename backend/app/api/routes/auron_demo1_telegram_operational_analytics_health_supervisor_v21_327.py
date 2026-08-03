from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import (
    _active_sequence_store,
    _circuit_store,
    _supervision_store,
)
from app.api.routes.auron_demo1_telegram_continuous_queue_orchestration_v21_324 import _queue_item_store
from app.api.routes.auron_demo1_telegram_dead_letter_replay_governance_v21_326 import _replay_store
from app.api.routes.auron_demo1_telegram_lifecycle_progression_worker_v21_325 import (
    _dead_letter_store,
    _progression_store,
)
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_operational_runtime_worker_v21_311 import _worker_run_store

router = APIRouter(prefix='/auron/demo1/v21.327', tags=['auron-demo1-telegram-operational-analytics-health-supervisor'])

_health_snapshot_store: dict[str, dict] = {}
_anomaly_store: dict[str, dict] = {}


class TelegramRuntimeHealthEvaluationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    max_failed_worker_calls: int = Field(default=3, ge=0, le=100)
    max_dead_letters: int = Field(default=2, ge=0, le=100)
    max_queue_backlog: int = Field(default=20, ge=1, le=1000)
    max_active_sequences: int = Field(default=1, ge=0, le=100)
    auto_pause_on_critical: bool = True


def reset_telegram_operational_analytics_health_supervisor_store() -> None:
    _health_snapshot_store.clear()
    _anomaly_store.clear()


def _chat_items(store: dict[str, dict], chat_id: str) -> list[dict]:
    return [item for item in store.values() if str(item.get('telegram_chat_id')) == str(chat_id)]


def _metrics(chat_id: str) -> dict:
    worker_runs = [item for item in _worker_run_store.values() if str(item.get('telegram_chat_id') or item.get('chat_id') or '') == str(chat_id)]
    queue_items = _chat_items(_queue_item_store, chat_id)
    progressions = _chat_items(_progression_store, chat_id)
    dead_letters = _chat_items(_dead_letter_store, chat_id)
    replays = _chat_items(_replay_store, chat_id)
    supervisions = _chat_items(_supervision_store, chat_id)
    completed_progressions = sum(1 for item in progressions if item.get('progression_state') == 'completed')
    total_progressions = len(progressions)
    return {
        'worker_runs': len(worker_runs),
        'failed_worker_calls': sum(1 for item in worker_runs if not item.get('accepted')),
        'successful_worker_calls': sum(1 for item in worker_runs if item.get('accepted')),
        'queue_backlog': sum(1 for item in queue_items if item.get('queue_state') in {'queued-awaiting-supervised-dispatch', 'dispatched-awaiting-lifecycle-progression', 'lifecycle-progression-running'}),
        'active_sequences': 1 if chat_id in _active_sequence_store else 0,
        'supervised_conversations': len(supervisions),
        'failed_supervisions': sum(1 for item in supervisions if item.get('supervision_state') == 'failed'),
        'progressions': total_progressions,
        'completed_progressions': completed_progressions,
        'completion_rate': completed_progressions / total_progressions if total_progressions else 0.0,
        'dead_letters': len(dead_letters),
        'replays': len(replays),
        'safety_circuit_state': _circuit_store.get(chat_id, {}).get('state', 'closed'),
    }


@router.post('/evaluate')
def evaluate_runtime_health(payload: TelegramRuntimeHealthEvaluationRequest) -> dict:
    go_live = _go_live_store.get(payload.telegram_chat_id)
    if go_live is None:
        raise HTTPException(status_code=404, detail='Telegram go-live acceptance not found for this chat')

    metrics = _metrics(payload.telegram_chat_id)
    checks = {
        'failed_worker_calls_within_limit': metrics['failed_worker_calls'] <= payload.max_failed_worker_calls,
        'dead_letters_within_limit': metrics['dead_letters'] <= payload.max_dead_letters,
        'queue_backlog_within_limit': metrics['queue_backlog'] <= payload.max_queue_backlog,
        'active_sequences_within_limit': metrics['active_sequences'] <= payload.max_active_sequences,
        'safety_circuit_closed': metrics['safety_circuit_state'] == 'closed',
    }
    blockers = [name for name, passed in checks.items() if not passed]
    critical = any(name in blockers for name in {'failed_worker_calls_within_limit', 'dead_letters_within_limit', 'safety_circuit_closed'})
    health_state = 'critical' if critical else ('degraded' if blockers else 'healthy')
    now = datetime.now(timezone.utc).isoformat()

    snapshot = {
        'health_snapshot_id': str(uuid4()),
        'telegram_chat_id': payload.telegram_chat_id,
        'go_live_acceptance_id': go_live.get('go_live_acceptance_id'),
        'metrics': metrics,
        'checks': checks,
        'blockers': blockers,
        'health_state': health_state,
        'evaluated_by': payload.actor,
        'evaluated_at': now,
        'external_calls_made': 0,
    }
    _health_snapshot_store[payload.telegram_chat_id] = snapshot

    anomaly = None
    if blockers:
        anomaly = {
            'anomaly_id': str(uuid4()),
            'health_snapshot_id': snapshot['health_snapshot_id'],
            'telegram_chat_id': payload.telegram_chat_id,
            'severity': health_state,
            'blockers': blockers,
            'metrics': metrics,
            'detected_at': now,
            'auto_pause_applied': False,
            'external_calls_made': 0,
        }
        _anomaly_store[anomaly['anomaly_id']] = anomaly

    if critical and payload.auto_pause_on_critical:
        go_live['continuous_mode_active'] = False
        go_live['go_live_state'] = 'paused-by-runtime-health-supervisor'
        go_live['paused_at'] = now
        go_live['pause_reason'] = 'critical-runtime-health-anomaly'
        circuit = _circuit_store.setdefault(payload.telegram_chat_id, {'telegram_chat_id': payload.telegram_chat_id})
        circuit.update(state='open', opened_at=now, opened_reason='runtime-health-critical')
        if anomaly is not None:
            anomaly['auto_pause_applied'] = True

    return {
        'state': f'telegram-runtime-health-{health_state}',
        'snapshot': snapshot,
        'anomaly': anomaly,
        'continuous_mode_active': bool(go_live.get('continuous_mode_active')),
        'external_calls_made': 0,
        'next_layer': 'runtime-health-remediation' if blockers else 'continuous-runtime-observation',
    }


@router.get('/status')
def runtime_health_status() -> dict:
    snapshots = list(_health_snapshot_store.values())
    return {
        'health_snapshots': len(snapshots),
        'healthy': sum(1 for item in snapshots if item.get('health_state') == 'healthy'),
        'degraded': sum(1 for item in snapshots if item.get('health_state') == 'degraded'),
        'critical': sum(1 for item in snapshots if item.get('health_state') == 'critical'),
        'anomalies': len(_anomaly_store),
        'auto_paused_chats': sum(1 for item in _go_live_store.values() if item.get('go_live_state') == 'paused-by-runtime-health-supervisor'),
        'external_calls_made': 0,
        'supervisor_mode': 'analytics-anomaly-detection-critical-auto-pause',
    }


@router.get('/analytics')
def operational_analytics() -> dict:
    chats = sorted(_go_live_store.keys())
    return {
        'chat_count': len(chats),
        'items': [{'telegram_chat_id': chat_id, 'metrics': _metrics(chat_id)} for chat_id in chats],
        'external_calls_made': 0,
    }


@router.get('/anomalies')
def list_anomalies() -> dict:
    items = sorted(_anomaly_store.values(), key=lambda item: item['detected_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_dead_letter_replay_governance_v21_326 import command_center as v21_326_command_center
    return v21_326_command_center().replace('v21.326', 'v21.327').replace('AURON TELEGRAM DEAD LETTER REPLAY GOVERNANCE COMMAND CENTER', 'AURON TELEGRAM OPERATIONAL ANALYTICS HEALTH SUPERVISOR COMMAND CENTER')
