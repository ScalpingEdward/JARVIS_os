from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_execution_queue_v21_251 import _queue, _ready_item
from app.api.routes.auron_demo1_safe_queue_runner_v21_252 import (
    _run_safe_batch,
    _runner_status,
    command_center as v21_252_command_center,
    dialogue as v21_252_dialogue,
)
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.253', tags=['auron-demo1-runner-checkpoints'])
CONTROL_CATEGORY = 'auron-runner-control'
CHECKPOINT_CATEGORY = 'auron-runner-checkpoint'


def _scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _records(req: DialogueRequest, category: str) -> list:
    required = _scope(req)
    items = [item for item in memory_service.list_all(category=category) if required.issubset(set(item.tags))]
    return sorted(items, key=lambda item: item.created_at)


def _replace_record(req: DialogueRequest, category: str, content: str, tags: list[str]) -> None:
    for item in _records(req, category):
        memory_service.delete(item.id)
    memory_service.create(MemoryCreate(
        content=content,
        category=category,
        priority=MemoryPriority.high,
        tags=[*_scope(req), *tags],
    ))


def _is_paused(req: DialogueRequest) -> bool:
    records = _records(req, CONTROL_CATEGORY)
    return bool(records and 'state:paused' in set(records[-1].tags))


def _set_paused(req: DialogueRequest, paused: bool) -> None:
    state = 'paused' if paused else 'active'
    _replace_record(req, CONTROL_CATEGORY, state, [f'state:{state}'])


def _checkpoint(req: DialogueRequest) -> dict | None:
    records = _records(req, CHECKPOINT_CATEGORY)
    if not records:
        return None
    item = records[-1]
    tags = set(item.tags)

    def value(prefix: str, default: str = '') -> str:
        return next((tag.split(':', 1)[1] for tag in tags if tag.startswith(prefix)), default)

    next_index = int(value('next-index:', '0') or 0)
    completed = int(value('completed:', '0') or 0)
    return {
        'completed': completed,
        'next_index': next_index or None,
        'stop_reason': value('stop:', 'unknown'),
        'last_mode': value('mode:', 'unknown'),
        'content': item.content,
    }


def _write_checkpoint(req: DialogueRequest, result: dict) -> dict:
    queue = _queue(req)
    ready = _ready_item(queue)
    completed = sum(1 for item in queue if item['status'] == 'completed')
    stop_reason = str(result.get('runner_stop_reason') or 'command')
    mode = str(result.get('mode') or 'unknown')
    next_index = ready['index'] if ready else 0
    content = ready['content'] if ready else 'queue-complete'
    _replace_record(
        req,
        CHECKPOINT_CATEGORY,
        content,
        [f'completed:{completed}', f'next-index:{next_index}', f'stop:{stop_reason}', f'mode:{mode}'],
    )
    return _checkpoint(req) or {}


def _status(req: DialogueRequest) -> dict:
    base = _runner_status(req)
    base['runner_paused'] = _is_paused(req)
    base['runner_checkpoint'] = _checkpoint(req)
    base['runner_resumable'] = bool(base['queue_ready_item'])
    return base


def _response(mode: str, reply: str, req: DialogueRequest, **extra) -> dict:
    status = _status(req)
    data = {
        'state': 'completed',
        'mode': mode,
        'reply': reply,
        'detected_intents': ['runner-checkpoint-control'],
        'steps': [],
        'approval_required': bool(status.get('runner_preview') and status['runner_preview'].get('approval_required')),
        **status,
    }
    data.update(extra)
    return data


def _controlled_run(req: DialogueRequest) -> dict:
    if _is_paused(req):
        checkpoint = _checkpoint(req)
        return _response(
            'queue-runner-paused',
            'Queue Runner ist pausiert. Nutze „Queue Runner fortsetzen“, um am gespeicherten Checkpoint weiterzumachen.',
            req,
            runner_stop_reason='paused',
            runner_checkpoint=checkpoint,
        )
    result = _run_safe_batch(req)
    checkpoint = _write_checkpoint(req, result)
    result['runner_paused'] = False
    result['runner_checkpoint'] = checkpoint
    result['runner_resumable'] = bool(_ready_item(_queue(req)))
    return result


def _control_command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())

    if normalized in {'pausiere queue runner', 'queue runner pausieren', 'pause queue runner', 'pause runner'}:
        _set_paused(req, True)
        checkpoint = _write_checkpoint(req, {'mode': 'queue-runner-paused', 'runner_stop_reason': 'operator-pause'})
        return _response(
            'queue-runner-paused',
            'Queue Runner pausiert. Queue und Fortschritt bleiben erhalten.',
            req,
            runner_checkpoint=checkpoint,
            runner_stop_reason='operator-pause',
        )

    if normalized in {'queue runner fortsetzen', 'runner fortsetzen', 'resume queue runner', 'resume runner'}:
        _set_paused(req, False)
        if not _ready_item(_queue(req)):
            checkpoint = _write_checkpoint(req, {'mode': 'queue-runner-resume-empty', 'runner_stop_reason': 'queue-complete'})
            return _response('queue-runner-resume-empty', 'Es gibt keinen offenen Queue-Schritt zum Fortsetzen.', req, runner_checkpoint=checkpoint)
        result = _run_safe_batch(req)
        checkpoint = _write_checkpoint(req, result)
        result['runner_paused'] = False
        result['runner_checkpoint'] = checkpoint
        result['runner_resumable'] = bool(_ready_item(_queue(req)))
        return result

    if normalized in {'queue checkpoint', 'zeige queue checkpoint', 'runner checkpoint', 'zeige runner checkpoint'}:
        checkpoint = _checkpoint(req)
        if checkpoint:
            reply = f"Checkpoint: {checkpoint['completed']} erledigt. Nächster Queue-Index: {checkpoint['next_index'] or 'keiner'}. Stop: {checkpoint['stop_reason']}."
        else:
            reply = 'Noch kein Runner-Checkpoint vorhanden.'
        return _response('queue-runner-checkpoint-read', reply, req)

    if normalized in {
        'starte sicheren queue run', 'starte safe queue run', 'führe sichere queue aus',
        'fuehre sichere queue aus', 'run safe queue', 'run queue safely',
    }:
        return _controlled_run(req)

    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _control_command(req)
    if direct is not None:
        return direct
    result = v21_252_dialogue(req)
    result.update(_status(req))
    return result


@router.get('/runner-checkpoint')
def runner_checkpoint(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano', risk_brain_hard_block: bool = False) -> dict:
    req = DialogueRequest(
        session_id=session_id,
        workspace_id=workspace_id,
        operator_id=operator_id,
        command='runner-checkpoint',
        risk_brain_hard_block=risk_brain_hard_block,
    )
    return _status(req)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_252_command_center()
    html = html.replace('v21.252', 'v21.253')
    html = html.replace('SAFE QUEUE RUNNER COMMAND CENTER', 'CHECKPOINTED QUEUE RUNNER COMMAND CENTER')
    html = html.replace(
        "E('approval').textContent=d.runner_classification==='approval-required'?'RUNNER · APPROVAL':(d.runner_classification==='blocked'?'RUNNER · BLOCKED':(d.execution_preview&&d.execution_preview.approval_required?'EXEC · APPROVAL':(d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO'))));",
        "E('approval').textContent=d.runner_paused?'RUNNER · PAUSED':(d.runner_classification==='approval-required'?'RUNNER · APPROVAL':(d.runner_classification==='blocked'?'RUNNER · BLOCKED':(d.execution_preview&&d.execution_preview.approval_required?'EXEC · APPROVAL':(d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO')))));",
    )
    return html


from app.api.routes.auron_demo1_provider_brain_v21_254 import router as _auron_v21_254_router
router.routes.extend(_auron_v21_254_router.routes)
