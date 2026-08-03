from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_queue_orchestration_v21_324 import _queue_item_store
from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_lifecycle_progression_worker_v21_325 import _dead_letter_store, _progression_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store

router = APIRouter(prefix='/auron/demo1/v21.326', tags=['auron-demo1-telegram-dead-letter-replay-governance'])
_replay_store: dict[str, dict] = {}
_REPLAY_PHRASE = 'REPLAY ONE AURON DEAD LETTER'


class TelegramDeadLetterReplayRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    progression_id: str = Field(min_length=1, max_length=160)
    replay_phrase: str = Field(min_length=1, max_length=200)
    recovery_evidence_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)


def reset_telegram_dead_letter_replay_governance_store() -> None:
    _replay_store.clear()


def _integrity_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/replay')
def replay_dead_letter(payload: TelegramDeadLetterReplayRequest) -> dict:
    if payload.replay_phrase != _REPLAY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit dead-letter replay approval required')
    existing = _replay_store.get(payload.progression_id)
    if existing is not None:
        return {'state': 'telegram-dead-letter-already-replayed', 'replay': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    dead = _dead_letter_store.get(payload.progression_id)
    progression = next((item for item in _progression_store.values() if item.get('progression_id') == payload.progression_id), None)
    if dead is None or progression is None:
        raise HTTPException(status_code=404, detail='Telegram dead-letter lifecycle not found')
    chat_id = dead['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    queue_item = next((item for item in _queue_item_store.values() if item.get('queue_item_id') == dead.get('queue_item_id')), None)
    checks = {
        'dead_letter_state_valid': progression.get('progression_state') == 'dead-lettered',
        'checkpoint_history_present': bool(dead.get('checkpoint_history')),
        'recovery_evidence_present': bool(payload.recovery_evidence_id),
        'go_live_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
        'queue_item_present': queue_item is not None,
        'queue_item_failed': bool(queue_item and queue_item.get('queue_state') == 'failed'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram dead-letter replay blocked', 'blockers': blockers})
    now = datetime.now(timezone.utc).isoformat()
    audit_payload = {
        'progression_id': payload.progression_id,
        'dead_letter_id': dead['dead_letter_id'],
        'queue_item_id': dead['queue_item_id'],
        'telegram_chat_id': chat_id,
        'failed_stage': dead.get('failed_stage'),
        'recovery_evidence_id': payload.recovery_evidence_id,
        'checks': checks,
        'reason': payload.reason,
    }
    record = {
        'replay_id': str(uuid4()),
        **audit_payload,
        'integrity_hash': _integrity_hash(audit_payload),
        'immutable': True,
        'replayed_by': payload.actor,
        'replayed_at': now,
        'external_calls_made': 0,
    }
    _replay_store[payload.progression_id] = record
    dead.update(replay_state='replayed', replay_id=record['replay_id'], replayed_at=now)
    progression.update(progression_state='running-awaiting-checkpoint', dead_letter_id=None, updated_at=now)
    queue_item.update(queue_state='lifecycle-progression-running', failure_reason=None, completed_at=None)
    return {'state': 'telegram-dead-letter-replay-authorized', 'replay': record, 'external_calls_made': 0, 'next_stage': progression.get('current_stage')}


@router.get('/metrics')
def replay_metrics() -> dict:
    progressions = list(_progression_store.values())
    total = len(progressions)
    completed = sum(1 for item in progressions if item.get('progression_state') == 'completed')
    dead_lettered = sum(1 for item in progressions if item.get('progression_state') == 'dead-lettered')
    return {
        'progressions': total,
        'completed': completed,
        'dead_lettered': dead_lettered,
        'replays': len(_replay_store),
        'completion_rate': completed / total if total else 0.0,
        'dead_letter_rate': dead_lettered / total if total else 0.0,
        'external_calls_made': 0,
    }


@router.get('/replays')
def list_replays() -> dict:
    return {'count': len(_replay_store), 'items': list(_replay_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_lifecycle_progression_worker_v21_325 import command_center as v21_325_command_center
    return v21_325_command_center().replace('v21.325', 'v21.326').replace('AURON TELEGRAM LIFECYCLE PROGRESSION WORKER COMMAND CENTER', 'AURON TELEGRAM DEAD LETTER REPLAY GOVERNANCE COMMAND CENTER')
