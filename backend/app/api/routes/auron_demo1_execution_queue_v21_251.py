from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_goal_aware_planning_v21_249 import _plan
from app.api.routes.auron_demo1_plan_execution_coordinator_v21_250 import (
    _preview,
    command_center as v21_250_command_center,
    dialogue as v21_250_dialogue,
)
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.251', tags=['auron-demo1-execution-queue'])
QUEUE_CATEGORY = 'auron-execution-queue'


def _scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _records(req: DialogueRequest) -> list:
    required = _scope(req)
    items = [item for item in memory_service.list_all(category=QUEUE_CATEGORY) if required.issubset(set(item.tags))]
    return sorted(items, key=lambda item: item.created_at)


def _clear(req: DialogueRequest) -> None:
    for item in _records(req):
        memory_service.delete(item.id)


def _queue(req: DialogueRequest) -> list[dict]:
    items = []
    for record in _records(req):
        tags = set(record.tags)
        index = int(next((x.split(':', 1)[1] for x in tags if x.startswith('index:')), '0'))
        plan_index = int(next((x.split(':', 1)[1] for x in tags if x.startswith('plan-index:')), '0'))
        classification = next((x.split(':', 1)[1] for x in tags if x.startswith('class:')), 'conversation/manual')
        status = next((x.split(':', 1)[1] for x in tags if x.startswith('status:')), 'queued')
        dependency = int(next((x.split(':', 1)[1] for x in tags if x.startswith('depends-on:')), '0'))
        items.append({
            'id': str(record.id), 'index': index, 'plan_index': plan_index, 'content': record.content,
            'classification': classification, 'status': status, 'depends_on': dependency or None,
        })
    return sorted(items, key=lambda x: x['index'])


def _set_status(req: DialogueRequest, item: dict, status: str) -> None:
    record = next(r for r in _records(req) if str(r.id) == item['id'])
    tags = [t for t in record.tags if not t.startswith('status:')]
    memory_service.delete(record.id)
    memory_service.create(MemoryCreate(content=record.content, category=QUEUE_CATEGORY, priority=record.priority, tags=[*tags, f'status:{status}']))


def _build_queue(req: DialogueRequest) -> list[dict]:
    _clear(req)
    scope = list(_scope(req))
    pending = [step for step in _plan(req) if step['status'] == 'pending']
    previous_index = 0
    for queue_index, step in enumerate(pending, start=1):
        probe = DialogueRequest(
            session_id=req.session_id, workspace_id=req.workspace_id, operator_id=req.operator_id,
            command='queue-preview', risk_brain_hard_block=req.risk_brain_hard_block,
        )
        # v21.250 previews the current pending plan step. For later steps we classify conservatively as manual
        # until they become current, avoiding speculative execution authority.
        preview = _preview(probe) if queue_index == 1 else {'classification': 'conversation/manual'}
        classification = preview.get('classification', 'conversation/manual')
        tags = [*scope, f'index:{queue_index}', f'plan-index:{step["index"]}', f'class:{classification}', 'status:queued']
        if previous_index:
            tags.append(f'depends-on:{previous_index}')
        memory_service.create(MemoryCreate(content=step['content'], category=QUEUE_CATEGORY, priority=MemoryPriority.high, tags=tags))
        previous_index = queue_index
    return _queue(req)


def _ready_item(queue: list[dict]) -> dict | None:
    completed = {item['index'] for item in queue if item['status'] == 'completed'}
    for item in queue:
        if item['status'] != 'queued':
            continue
        dep = item.get('depends_on')
        if dep is None or dep in completed:
            return item
    return None


def _summary(queue: list[dict]) -> str:
    if not queue:
        return 'Execution Queue ist leer.'
    parts = []
    for item in queue:
        dep = f" dep:{item['depends_on']}" if item.get('depends_on') else ''
        parts.append(f"{item['index']}. {item['status']} · {item['classification']}{dep} · {item['content']}")
    return 'Queue: ' + ' | '.join(parts)


def _response(mode: str, reply: str, req: DialogueRequest, **extra) -> dict:
    queue = _queue(req)
    ready = _ready_item(queue)
    data = {
        'state': 'completed', 'mode': mode, 'reply': reply,
        'detected_intents': ['execution-queue'], 'steps': [], 'approval_required': False,
        'execution_queue': queue, 'queue_count': len(queue),
        'queue_completed_count': sum(1 for x in queue if x['status'] == 'completed'),
        'queue_ready_item': ready,
    }
    data.update(extra)
    return data


def _queue_command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())
    if normalized in {'baue execution queue', 'erstelle execution queue', 'queue erstellen', 'build execution queue', 'prepare execution queue'}:
        queue = _build_queue(req)
        ready = _ready_item(queue)
        return _response('execution-queue-built', f'Execution Queue erstellt. {len(queue)} Schritte. Bereit: {ready["content"] if ready else "kein Schritt"}.', req)

    if normalized in {'zeige execution queue', 'zeig execution queue', 'zeige queue', 'zeig queue', 'show execution queue', 'show queue'}:
        return _response('execution-queue-read', _summary(_queue(req)), req)

    if normalized in {'was ist bereit', 'welcher schritt ist bereit', 'nächster queue schritt', 'naechster queue schritt', 'what is ready', 'next queue item'}:
        ready = _ready_item(_queue(req))
        reply = f'Bereiter Queue-Schritt: {ready["content"]}.' if ready else 'Aktuell ist kein Queue-Schritt bereit.'
        return _response('execution-queue-ready-read', reply, req)

    if normalized in {'queue schritt erledigt', 'aktuellen queue schritt erledigt', 'queue item done'}:
        queue = _queue(req)
        ready = _ready_item(queue)
        if not ready:
            return _response('execution-queue-complete-none', 'Kein bereiter Queue-Schritt vorhanden.', req)
        _set_status(req, ready, 'completed')
        updated = _queue(req)
        nxt = _ready_item(updated)
        reply = 'Queue-Schritt abgeschlossen.' + (f' Als Nächstes bereit: {nxt["content"]}.' if nxt else ' Keine weiteren Schritte bereit.')
        return _response('execution-queue-item-completed', reply, req)

    if normalized in {'queue löschen', 'queue loeschen', 'queue zurücksetzen', 'queue zuruecksetzen', 'clear queue', 'reset queue'}:
        _clear(req)
        return _response('execution-queue-cleared', 'Execution Queue wurde gelöscht.', req)
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _queue_command(req)
    if direct is not None:
        return direct
    result = v21_250_dialogue(req)
    queue = _queue(req)
    result['execution_queue'] = queue
    result['queue_count'] = len(queue)
    result['queue_completed_count'] = sum(1 for x in queue if x['status'] == 'completed')
    result['queue_ready_item'] = _ready_item(queue)
    return result


@router.get('/execution-queue')
def execution_queue(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='queue-view')
    queue = _queue(req)
    return {
        'active': bool(queue), 'count': len(queue),
        'completed': sum(1 for x in queue if x['status'] == 'completed'),
        'ready_item': _ready_item(queue), 'items': queue,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_250_command_center()
    html = html.replace('v21.250', 'v21.251')
    html = html.replace('PLAN EXECUTION COMMAND CENTER', 'EXECUTION QUEUE COMMAND CENTER')
    html = html.replace(
        "E('intent').textContent=d.plan_active?'PLAN · '+(d.plan_done_count||0)+'/'+(d.plan_step_count||0):(d.goal?'GOAL · ACTIVE':'INTENTS · '+intents.length);",
        "E('intent').textContent=d.queue_count?'QUEUE · '+(d.queue_completed_count||0)+'/'+d.queue_count:(d.plan_active?'PLAN · '+(d.plan_done_count||0)+'/'+(d.plan_step_count||0):(d.goal?'GOAL · ACTIVE':'INTENTS · '+intents.length));"
    )
    return html


from app.api.routes.auron_demo1_safe_queue_runner_v21_252 import router as _auron_v21_252_router
router.routes.extend(_auron_v21_252_router.routes)
