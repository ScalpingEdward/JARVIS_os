from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_provider_brain_v21_254 import (
    command_center as v21_254_command_center,
    dialogue as v21_254_dialogue,
)
from app.api.routes.auron_demo1_runner_checkpoints_v21_253 import _controlled_run, _status
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.255', tags=['auron-demo1-retry-recovery'])
RECOVERY_CATEGORY = 'auron-runner-recovery'
MAX_RETRIES = 2
NON_RETRYABLE = {'approval-required', 'blocked', 'conversation/manual', 'paused', 'empty', 'queue-complete', 'batch-limit'}


def _scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _records(req: DialogueRequest) -> list:
    required = _scope(req)
    items = [x for x in memory_service.list_all(category=RECOVERY_CATEGORY) if required.issubset(set(x.tags))]
    return sorted(items, key=lambda x: x.created_at)


def _recovery(req: DialogueRequest) -> dict:
    items = _records(req)
    if not items:
        return {'retry_count': 0, 'last_stop_reason': None, 'last_mode': None, 'retryable': False}
    item = items[-1]
    tags = set(item.tags)
    def value(prefix: str, default: str = '') -> str:
        return next((t.split(':', 1)[1] for t in tags if t.startswith(prefix)), default)
    count = int(value('retry-count:', '0') or 0)
    reason = value('stop:', '') or None
    mode = value('mode:', '') or None
    return {
        'retry_count': count,
        'last_stop_reason': reason,
        'last_mode': mode,
        'retryable': bool(reason and reason not in NON_RETRYABLE and count < MAX_RETRIES),
    }


def _write_recovery(req: DialogueRequest, result: dict, retry_count: int) -> dict:
    for item in _records(req):
        memory_service.delete(item.id)
    reason = str(result.get('runner_stop_reason') or result.get('mode') or 'unknown')
    mode = str(result.get('mode') or 'unknown')
    memory_service.create(MemoryCreate(
        content=reason,
        category=RECOVERY_CATEGORY,
        priority=MemoryPriority.high,
        tags=[*_scope(req), f'retry-count:{retry_count}', f'stop:{reason}', f'mode:{mode}'],
    ))
    return _recovery(req)


def _reset_recovery(req: DialogueRequest) -> None:
    for item in _records(req):
        memory_service.delete(item.id)


def _run_with_recovery(req: DialogueRequest, allow_retry: bool) -> dict:
    before = _status(req)
    completed_before = int(before.get('queue_completed_count') or 0)
    result = _controlled_run(req)
    after = _status(req)
    completed_after = int(after.get('queue_completed_count') or 0)

    if completed_after > completed_before:
        _reset_recovery(req)
        result['recovery'] = _recovery(req)
        return result

    reason = str(result.get('runner_stop_reason') or result.get('mode') or 'unknown')
    recovery = _recovery(req)
    count = recovery['retry_count']

    if reason in NON_RETRYABLE:
        result['recovery'] = _write_recovery(req, result, count)
        result['recovery_action'] = 'stop-non-retryable'
        return result

    if not allow_retry:
        result['recovery'] = _write_recovery(req, result, count)
        result['recovery_action'] = 'retry-available' if count < MAX_RETRIES else 'retry-limit-reached'
        return result

    attempts = 0
    while attempts < MAX_RETRIES and count < MAX_RETRIES:
        attempts += 1
        count += 1
        retry_result = _controlled_run(req)
        retry_after = _status(req)
        if int(retry_after.get('queue_completed_count') or 0) > completed_after:
            _reset_recovery(req)
            retry_result['recovery'] = _recovery(req)
            retry_result['recovery_action'] = 'recovered'
            retry_result['recovery_attempts_this_run'] = attempts
            return retry_result
        reason = str(retry_result.get('runner_stop_reason') or retry_result.get('mode') or 'unknown')
        result = retry_result
        if reason in NON_RETRYABLE:
            break

    result['recovery'] = _write_recovery(req, result, count)
    result['recovery_action'] = 'retry-limit-reached' if count >= MAX_RETRIES else 'stopped'
    result['recovery_attempts_this_run'] = attempts
    return result


def _command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())
    if normalized in {'recovery status', 'zeige recovery status', 'retry status'}:
        recovery = _recovery(req)
        reply = f"Recovery: {recovery['retry_count']}/{MAX_RETRIES} Retries. Letzter Stop: {recovery['last_stop_reason'] or 'keiner'}."
        return {'state':'completed','mode':'recovery-status','reply':reply,'detected_intents':['retry-recovery'],'steps':[],'approval_required':False,'recovery':recovery}
    if normalized in {'retry letzten fehler', 'wiederhole letzten fehler', 'retry last failure'}:
        recovery = _recovery(req)
        if not recovery['retryable']:
            return {'state':'completed','mode':'recovery-not-retryable','reply':'Der letzte Stop ist nicht retry-fähig oder das Retry-Limit ist erreicht.','detected_intents':['retry-recovery'],'steps':[],'approval_required':False,'recovery':recovery}
        return _run_with_recovery(req, allow_retry=True)
    if normalized in {'retry zurücksetzen', 'retry zuruecksetzen', 'reset retry', 'reset recovery'}:
        _reset_recovery(req)
        return {'state':'completed','mode':'recovery-reset','reply':'Retry-/Recovery-Status wurde zurückgesetzt.','detected_intents':['retry-recovery'],'steps':[],'approval_required':False,'recovery':_recovery(req)}
    if normalized in {'starte resilienten queue run', 'führe resilienten queue run aus', 'fuehre resilienten queue run aus', 'run resilient queue'}:
        return _run_with_recovery(req, allow_retry=True)
    if normalized in {'starte sicheren queue run', 'starte safe queue run', 'führe sichere queue aus', 'fuehre sichere queue aus', 'run safe queue', 'run queue safely'}:
        return _run_with_recovery(req, allow_retry=False)
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _command(req)
    if direct is not None:
        return direct
    result = v21_254_dialogue(req)
    result['recovery'] = _recovery(req)
    return result


@router.get('/recovery-status')
def recovery_status(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='recovery-status')
    return {'max_retries': MAX_RETRIES, **_recovery(req)}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_254_command_center()
    html = html.replace('v21.254', 'v21.255')
    html = html.replace('PROVIDER-NATIVE AURON COMMAND CENTER', 'RESILIENT AURON COMMAND CENTER')
    return html


# v21.256 extends the already registered v21.255 router after all v21.255 symbols exist.
from app.api.routes.auron_demo1_health_supervisor_v21_256 import router as _auron_v21_256_router
router.routes.extend(_auron_v21_256_router.routes)
