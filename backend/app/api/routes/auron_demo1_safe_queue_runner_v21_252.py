from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_execution_queue_v21_251 import (
    _queue,
    _ready_item,
    _set_status,
    command_center as v21_251_command_center,
    dialogue as v21_251_dialogue,
)
from app.api.routes.auron_demo1_plan_execution_coordinator_v21_250 import _execution_command, _preview

router = APIRouter(prefix='/auron/demo1/v21.252', tags=['auron-demo1-safe-queue-runner'])
MAX_BATCH_STEPS = 5


def _runner_status(req: DialogueRequest) -> dict:
    queue = _queue(req)
    ready = _ready_item(queue)
    preview = _preview(req) if ready else None
    return {
        'queue_count': len(queue),
        'queue_completed_count': sum(1 for x in queue if x['status'] == 'completed'),
        'queue_ready_item': ready,
        'runner_ready': bool(ready),
        'runner_classification': preview.get('classification') if preview else None,
        'runner_preview': preview,
    }


def _response(mode: str, reply: str, req: DialogueRequest, **extra) -> dict:
    status = _runner_status(req)
    data = {
        'state': 'completed',
        'mode': mode,
        'reply': reply,
        'detected_intents': ['safe-queue-runner'],
        'steps': [],
        'approval_required': bool(status['runner_preview'] and status['runner_preview'].get('approval_required')),
        **status,
    }
    data.update(extra)
    return data


def _run_safe_batch(req: DialogueRequest) -> dict:
    queue = _queue(req)
    if not queue:
        return _response('queue-runner-empty', 'Execution Queue ist leer. Erstelle zuerst eine Queue.', req, runner_stop_reason='empty')

    executed: list[dict] = []
    stop_reason = 'completed-or-limit'

    for _ in range(MAX_BATCH_STEPS):
        queue = _queue(req)
        ready = _ready_item(queue)
        if ready is None:
            stop_reason = 'queue-complete'
            break

        preview = _preview(req)
        classification = preview.get('classification')
        if classification != 'safe-capability':
            stop_reason = classification or 'not-safe'
            break

        execution = _execution_command(DialogueRequest(
            session_id=req.session_id,
            workspace_id=req.workspace_id,
            operator_id=req.operator_id,
            command='Führe nächsten Planschritt aus',
            risk_brain_hard_block=req.risk_brain_hard_block,
        ))
        if not execution or execution.get('mode') != 'plan-execution-completed':
            stop_reason = execution.get('mode', 'execution-failed') if execution else 'execution-failed'
            break

        # Queue progress follows only a confirmed completed governed plan execution.
        current_queue = _queue(req)
        current_ready = _ready_item(current_queue)
        if current_ready and current_ready['index'] == ready['index']:
            _set_status(req, current_ready, 'completed')

        executed.append({
            'queue_index': ready['index'],
            'content': ready['content'],
            'classification': classification,
            'execution_state': execution.get('execution_state', 'completed'),
        })
    else:
        stop_reason = 'batch-limit'

    if executed:
        reply = f'Sicherer Queue-Run: {len(executed)} Schritt(e) abgeschlossen.'
    else:
        reply = 'Kein Queue-Schritt wurde ausgeführt.'

    status = _runner_status(req)
    if status['queue_ready_item']:
        reply += f" Nächster Schritt: {status['queue_ready_item']['content']}."
    else:
        reply += ' Keine weiteren Queue-Schritte sind bereit.'

    if stop_reason in {'approval-required', 'blocked', 'conversation/manual'}:
        reply += f' Runner gestoppt: {stop_reason}.'
    elif stop_reason == 'batch-limit':
        reply += f' Sicherheitslimit von {MAX_BATCH_STEPS} Schritten erreicht.'

    return _response(
        'queue-runner-completed' if executed else 'queue-runner-stopped',
        reply,
        req,
        runner_executed=executed,
        runner_executed_count=len(executed),
        runner_stop_reason=stop_reason,
        runner_batch_limit=MAX_BATCH_STEPS,
    )


def _runner_command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())
    if normalized in {
        'starte sicheren queue run', 'starte safe queue run', 'führe sichere queue aus',
        'fuehre sichere queue aus', 'run safe queue', 'run queue safely',
    }:
        return _run_safe_batch(req)
    if normalized in {'queue runner status', 'zeige queue runner status', 'safe runner status'}:
        status = _runner_status(req)
        ready = status['queue_ready_item']
        reply = f"Runner bereit. Nächster Schritt: {ready['content']}. Klassifikation: {status['runner_classification']}." if ready else 'Runner hat aktuell keinen bereiten Queue-Schritt.'
        return _response('queue-runner-status', reply, req)
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _runner_command(req)
    if direct is not None:
        return direct
    result = v21_251_dialogue(req)
    result.update(_runner_status(req))
    return result


@router.get('/queue-runner')
def queue_runner(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano', risk_brain_hard_block: bool = False) -> dict:
    req = DialogueRequest(
        session_id=session_id, workspace_id=workspace_id, operator_id=operator_id,
        command='queue-runner-status', risk_brain_hard_block=risk_brain_hard_block,
    )
    return _runner_status(req)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_251_command_center()
    html = html.replace('v21.251', 'v21.252')
    html = html.replace('EXECUTION QUEUE COMMAND CENTER', 'SAFE QUEUE RUNNER COMMAND CENTER')
    html = html.replace(
        "E('approval').textContent=d.execution_preview&&d.execution_preview.approval_required?'EXEC · APPROVAL':(d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO'));",
        "E('approval').textContent=d.runner_classification==='approval-required'?'RUNNER · APPROVAL':(d.runner_classification==='blocked'?'RUNNER · BLOCKED':(d.execution_preview&&d.execution_preview.approval_required?'EXEC · APPROVAL':(d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO'))));"
    )
    return html
