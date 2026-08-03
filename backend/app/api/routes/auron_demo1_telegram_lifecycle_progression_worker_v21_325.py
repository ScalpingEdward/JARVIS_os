from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_queue_orchestration_v21_324 import _queue_item_store
from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store

router = APIRouter(prefix='/auron/demo1/v21.325', tags=['auron-demo1-telegram-lifecycle-progression-worker'])
_progression_store: dict[str, dict] = {}
_dead_letter_store: dict[str, dict] = {}
_STAGES = ['conversation-dispatch','delivery-admission','execution-preparation','runtime-worker','result-correlation','lifecycle-closure']
_MAX_RECOVERY_ATTEMPTS = 3

class TelegramLifecycleProgressionStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    queue_item_id: str = Field(min_length=1, max_length=160)

class TelegramLifecycleCheckpointRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    progression_id: str = Field(min_length=1, max_length=160)
    stage: str = Field(min_length=1, max_length=120)
    success: bool
    evidence_id: str | None = Field(default=None, max_length=200)
    failure_reason: str | None = Field(default=None, max_length=500)
    retryable: bool = True

class TelegramLifecycleRecoveryRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    progression_id: str = Field(min_length=1, max_length=160)

def reset_telegram_lifecycle_progression_worker_store() -> None:
    _progression_store.clear(); _dead_letter_store.clear()

def _queue_item_by_id(queue_item_id: str) -> dict | None:
    return next((item for item in _queue_item_store.values() if item.get('queue_item_id') == queue_item_id), None)

def _progression_by_id(progression_id: str) -> dict | None:
    return next((item for item in _progression_store.values() if item.get('progression_id') == progression_id), None)

def _ensure_runtime_allowed(chat_id: str) -> None:
    go_live = _go_live_store.get(chat_id)
    if go_live is None or not go_live.get('continuous_mode_active'):
        raise HTTPException(status_code=409, detail='Active Telegram continuous-mode go-live acceptance required')
    if _circuit_store.get(chat_id, {}).get('state', 'closed') != 'closed':
        raise HTTPException(status_code=409, detail='Telegram safety circuit is open for this chat')

def _dead_letter(record: dict, actor: str, reason: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    dead = {'dead_letter_id': str(uuid4()), 'progression_id': record['progression_id'], 'queue_item_id': record['queue_item_id'], 'update_id': record['update_id'], 'telegram_chat_id': record['telegram_chat_id'], 'failed_stage': record['current_stage'], 'reason': reason, 'recovery_attempts': record['recovery_attempts'], 'checkpoint_history': list(record['checkpoint_history']), 'dead_lettered_by': actor, 'dead_lettered_at': now, 'external_calls_made': 0}
    _dead_letter_store[record['progression_id']] = dead
    record.update(progression_state='dead-lettered', dead_letter_id=dead['dead_letter_id'], completed_at=now)
    item = _queue_item_by_id(record['queue_item_id'])
    if item is not None: item.update(queue_state='failed', failure_reason=reason, completed_at=now)
    return dead

@router.post('/start')
def start_lifecycle_progression(payload: TelegramLifecycleProgressionStartRequest) -> dict:
    item = _queue_item_by_id(payload.queue_item_id)
    if item is None: raise HTTPException(status_code=404, detail='Telegram continuous queue item not found')
    existing = _progression_store.get(payload.queue_item_id)
    if existing is not None: return {'state':'telegram-lifecycle-progression-already-started','progression':existing,'idempotent_replay':True,'external_calls_made':0}
    if item.get('queue_state') != 'dispatched-awaiting-lifecycle-progression': raise HTTPException(status_code=409, detail='Telegram queue item is not awaiting lifecycle progression')
    _ensure_runtime_allowed(item['telegram_chat_id'])
    now = datetime.now(timezone.utc).isoformat()
    record = {'progression_id':str(uuid4()),'queue_item_id':item['queue_item_id'],'update_id':item['update_id'],'telegram_chat_id':item['telegram_chat_id'],'current_stage_index':0,'current_stage':_STAGES[0],'completed_stages':[],'checkpoint_history':[],'recovery_attempts':0,'progression_state':'running-awaiting-checkpoint','started_by':payload.actor,'started_at':now,'updated_at':now,'completed_at':None,'external_calls_made':0}
    _progression_store[payload.queue_item_id]=record; item.update(queue_state='lifecycle-progression-running', progression_id=record['progression_id'])
    return {'state':'telegram-lifecycle-progression-started','progression':record,'external_calls_made':0,'next_stage':record['current_stage']}

@router.post('/checkpoint')
def commit_lifecycle_checkpoint(payload: TelegramLifecycleCheckpointRequest) -> dict:
    record = _progression_by_id(payload.progression_id)
    if record is None: raise HTTPException(status_code=404, detail='Telegram lifecycle progression not found')
    if record.get('progression_state') in {'completed','dead-lettered'}: return {'state':'telegram-lifecycle-progression-already-terminal','progression':record,'idempotent_replay':True,'external_calls_made':0}
    if payload.stage != record.get('current_stage'): raise HTTPException(status_code=409, detail={'message':'Lifecycle checkpoint stage mismatch','expected_stage':record.get('current_stage'),'received_stage':payload.stage})
    _ensure_runtime_allowed(record['telegram_chat_id'])
    now=datetime.now(timezone.utc).isoformat(); checkpoint={'checkpoint_id':str(uuid4()),'stage':payload.stage,'success':payload.success,'evidence_id':payload.evidence_id,'failure_reason':payload.failure_reason,'retryable':payload.retryable,'committed_by':payload.actor,'committed_at':now}
    record['checkpoint_history'].append(checkpoint); record['updated_at']=now
    if not payload.success:
        reason=payload.failure_reason or 'unspecified-stage-failure'; record.update(progression_state='recovery-required' if payload.retryable else 'failed-non-retryable', last_failure_reason=reason)
        if not payload.retryable:
            dead=_dead_letter(record,payload.actor,reason); return {'state':'telegram-lifecycle-progression-dead-lettered','progression':record,'dead_letter':dead,'external_calls_made':0}
        return {'state':'telegram-lifecycle-progression-recovery-required','progression':record,'external_calls_made':0,'next_layer':'controlled-stage-recovery'}
    record['completed_stages'].append(payload.stage); record['recovery_attempts']=0; next_index=int(record['current_stage_index'])+1
    if next_index >= len(_STAGES):
        record.update(progression_state='completed',current_stage_index=len(_STAGES),current_stage=None,completed_at=now)
        item=_queue_item_by_id(record['queue_item_id'])
        if item is not None: item.update(queue_state='completed',completed_at=now,failure_reason=None)
        return {'state':'telegram-lifecycle-progression-completed','progression':record,'external_calls_made':0}
    record.update(current_stage_index=next_index,current_stage=_STAGES[next_index],progression_state='running-awaiting-checkpoint')
    return {'state':'telegram-lifecycle-checkpoint-committed','progression':record,'external_calls_made':0,'next_stage':record['current_stage']}

@router.post('/recover')
def recover_lifecycle_stage(payload: TelegramLifecycleRecoveryRequest) -> dict:
    record=_progression_by_id(payload.progression_id)
    if record is None: raise HTTPException(status_code=404, detail='Telegram lifecycle progression not found')
    if record.get('progression_state')=='dead-lettered': return {'state':'telegram-lifecycle-progression-already-dead-lettered','progression':record,'idempotent_replay':True,'external_calls_made':0}
    if record.get('progression_state')!='recovery-required': raise HTTPException(status_code=409, detail='Telegram lifecycle progression is not awaiting recovery')
    _ensure_runtime_allowed(record['telegram_chat_id']); record['recovery_attempts']+=1; record['updated_at']=datetime.now(timezone.utc).isoformat()
    if record['recovery_attempts'] > _MAX_RECOVERY_ATTEMPTS:
        dead=_dead_letter(record,payload.actor,record.get('last_failure_reason') or 'recovery-attempts-exhausted'); return {'state':'telegram-lifecycle-progression-dead-lettered','progression':record,'dead_letter':dead,'external_calls_made':0}
    record['progression_state']='running-awaiting-checkpoint'
    return {'state':'telegram-lifecycle-stage-recovery-authorized','progression':record,'external_calls_made':0,'retry_stage':record['current_stage'],'remaining_recovery_attempts':_MAX_RECOVERY_ATTEMPTS-record['recovery_attempts']}

@router.get('/status')
def lifecycle_progression_status() -> dict:
    items=list(_progression_store.values())
    return {'progressions':len(items),'running':sum(1 for i in items if i.get('progression_state')=='running-awaiting-checkpoint'),'recovery_required':sum(1 for i in items if i.get('progression_state')=='recovery-required'),'completed':sum(1 for i in items if i.get('progression_state')=='completed'),'dead_lettered':len(_dead_letter_store),'max_recovery_attempts':_MAX_RECOVERY_ATTEMPTS,'external_calls_made':0,'worker_mode':'checkpointed-supervised-recoverable-lifecycle-progression'}

@router.get('/progressions')
def list_progressions() -> dict:
    return {'count':len(_progression_store),'items':sorted(_progression_store.values(),key=lambda i:i['started_at']),'external_calls_made':0}

@router.get('/dead-letters')
def list_dead_letters() -> dict:
    return {'count':len(_dead_letter_store),'items':list(_dead_letter_store.values()),'external_calls_made':0}

@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_continuous_queue_orchestration_v21_324 import command_center as v21_324_command_center
    return v21_324_command_center().replace('v21.324','v21.325').replace('AURON TELEGRAM CONTINUOUS QUEUE ORCHESTRATION COMMAND CENTER','AURON TELEGRAM LIFECYCLE PROGRESSION WORKER COMMAND CENTER')
