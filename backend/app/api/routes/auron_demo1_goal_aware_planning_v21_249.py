from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.249', tags=['auron-demo1-goal-aware-planning'])
PLAN_CATEGORY = 'auron-goal-plan'


def _state(req: DialogueRequest) -> dict:
    from app.api.routes.auron_demo1_conversation_state_v21_248 import _state as state_fn
    return state_fn(req)


def _set_state(req: DialogueRequest, kind: str, content: str) -> None:
    from app.api.routes.auron_demo1_conversation_state_v21_248 import _set as set_fn
    set_fn(req, kind, content)


def _scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _plan_records(req: DialogueRequest) -> list:
    required = _scope(req)
    items = [
        item for item in memory_service.list_all(category=PLAN_CATEGORY)
        if required.issubset(set(item.tags))
    ]
    return sorted(items, key=lambda item: item.created_at)


def _clear_plan(req: DialogueRequest) -> None:
    for item in _plan_records(req):
        memory_service.delete(item.id)


def _plan(req: DialogueRequest) -> list[dict]:
    result = []
    for item in _plan_records(req):
        tags = set(item.tags)
        index_tag = next((tag for tag in tags if tag.startswith('index:')), 'index:0')
        status = 'done' if 'status:done' in tags else 'pending'
        result.append({
            'id': str(item.id),
            'index': int(index_tag.split(':', 1)[1]),
            'content': item.content,
            'status': status,
        })
    return sorted(result, key=lambda step: step['index'])


def _build_steps(req: DialogueRequest) -> list[str]:
    state = _state(req)
    goal = state['goal']
    if not goal:
        return []

    steps: list[str] = []
    if state['task']:
        steps.append(f'Aktuellen Fokus abschließen: {state["task"]}')
    if state['next_step']:
        steps.append(state['next_step'])
    steps.extend([
        f'Ergebnis gegen Ziel prüfen: {goal}',
        'Offene Lücken identifizieren und priorisieren',
        'Nächsten konkreten Umsetzungsschritt festlegen',
    ])

    unique: list[str] = []
    seen: set[str] = set()
    for step in steps:
        key = step.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(step.strip())
    return unique[:5]


def _store_plan(req: DialogueRequest, steps: list[str]) -> list[dict]:
    _clear_plan(req)
    scope = list(_scope(req))
    for index, step in enumerate(steps, start=1):
        memory_service.create(MemoryCreate(
            content=step,
            category=PLAN_CATEGORY,
            priority=MemoryPriority.high,
            tags=[*scope, f'index:{index}', 'status:pending'],
        ))
    return _plan(req)


def _current_step(plan: list[dict]) -> dict | None:
    return next((step for step in plan if step['status'] == 'pending'), None)


def _summary(plan: list[dict]) -> str:
    if not plan:
        return 'Noch kein aktiver Plan vorhanden.'
    lines = [
        f"{step['index']}. {'✓' if step['status'] == 'done' else '→'} {step['content']}"
        for step in plan
    ]
    return 'Plan: ' + ' | '.join(lines)


def _response(mode: str, reply: str, req: DialogueRequest) -> dict:
    plan = _plan(req)
    current = _current_step(plan)
    state = _state(req)
    return {
        'state': 'completed',
        'mode': mode,
        'reply': reply,
        'detected_intents': ['goal-aware-planning'],
        'steps': [],
        'approval_required': False,
        'conversation_state': state,
        'goal': state['goal'],
        'current_task': state['task'],
        'next_step': state['next_step'],
        'plan_active': bool(plan),
        'plan_steps': plan,
        'plan_step_count': len(plan),
        'plan_done_count': sum(1 for step in plan if step['status'] == 'done'),
        'plan_current_step': current['content'] if current else None,
    }


def _planning_command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())

    if normalized in {
        'plane unser ziel', 'plane mein ziel', 'erstelle einen plan', 'erstelle den plan',
        'mach einen plan', 'plan our goal', 'create a plan', 'build the plan',
    }:
        state = _state(req)
        if not state['goal']:
            return _response('goal-plan-missing-goal', 'Setze zuerst ein aktuelles Ziel, dann kann ich daraus einen Plan ableiten.', req)
        plan = _store_plan(req, _build_steps(req))
        current = _current_step(plan)
        if current:
            _set_state(req, 'next-step', current['content'])
        return _response('goal-plan-created', f'Plan erstellt. {len(plan)} Schritte. Als Nächstes: {current["content"] if current else "kein offener Schritt"}.', req)

    if normalized in {'zeig plan', 'zeige plan', 'was ist der plan', 'show plan', 'show the plan'}:
        return _response('goal-plan-read', _summary(_plan(req)), req)

    if normalized in {'was ist der nächste planschritt', 'was ist der naechste planschritt', 'nächster planschritt', 'naechster planschritt', 'next plan step'}:
        current = _current_step(_plan(req))
        reply = f'Nächster Planschritt: {current["content"]}.' if current else 'Es gibt aktuell keinen offenen Planschritt.'
        return _response('goal-plan-next-read', reply, req)

    if normalized in {'planschritt erledigt', 'aktueller planschritt erledigt', 'schritt erledigt', 'plan step done'}:
        plan = _plan(req)
        current = _current_step(plan)
        if current is None:
            return _response('goal-plan-step-complete', 'Es gibt aktuell keinen offenen Planschritt.', req)
        record = next(item for item in _plan_records(req) if str(item.id) == current['id'])
        memory_service.delete(record.id)
        memory_service.create(MemoryCreate(
            content=record.content,
            category=PLAN_CATEGORY,
            priority=record.priority,
            tags=[tag for tag in record.tags if tag != 'status:pending'] + ['status:done'],
        ))
        updated = _plan(req)
        next_step = _current_step(updated)
        if next_step:
            _set_state(req, 'next-step', next_step['content'])
            reply = f'Planschritt abgeschlossen. Als Nächstes: {next_step["content"]}.'
        else:
            _set_state(req, 'next-step', 'Plan abgeschlossen – Zielergebnis prüfen')
            reply = 'Alle Planschritte sind abgeschlossen. Jetzt Zielergebnis prüfen.'
        return _response('goal-plan-step-complete', reply, req)

    if normalized in {'plan löschen', 'plan loeschen', 'plan zurücksetzen', 'plan zuruecksetzen', 'clear plan', 'reset plan'}:
        _clear_plan(req)
        return _response('goal-plan-cleared', 'Aktiver Plan wurde gelöscht.', req)

    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    from app.api.routes.auron_demo1_conversation_state_v21_248 import dialogue as v21_248_dialogue

    direct = _planning_command(req)
    if direct is not None:
        return direct
    result = v21_248_dialogue(req)
    plan = _plan(req)
    current = _current_step(plan)
    result['plan_active'] = bool(plan)
    result['plan_steps'] = plan
    result['plan_step_count'] = len(plan)
    result['plan_done_count'] = sum(1 for step in plan if step['status'] == 'done')
    result['plan_current_step'] = current['content'] if current else None
    return result


@router.get('/plan')
def plan(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='plan-view')
    items = _plan(req)
    current = _current_step(items)
    return {
        'active': bool(items),
        'count': len(items),
        'done': sum(1 for step in items if step['status'] == 'done'),
        'current_step': current['content'] if current else None,
        'steps': items,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_conversation_state_v21_248 import command_center as v21_248_command_center

    html = v21_248_command_center()
    html = html.replace('v21.248', 'v21.249')
    html = html.replace('MISSION STATE COMMAND CENTER', 'GOAL-AWARE PLANNING COMMAND CENTER')
    html = html.replace(
        "E('processes').textContent=steps.length?steps.map((s,i)=>(i+1)+'. '+(s.intent||s.capability)+' ['+s.state+']').join('\\n'):(d.current_task?'FOCUS > '+d.current_task+(d.next_step?'\\nNEXT > '+d.next_step:''):'No active execution.');",
        "E('processes').textContent=steps.length?steps.map((s,i)=>(i+1)+'. '+(s.intent||s.capability)+' ['+s.state+']').join('\\n'):(d.plan_current_step?'PLAN > '+d.plan_current_step+(d.next_step?'\\nNEXT > '+d.next_step:''):(d.current_task?'FOCUS > '+d.current_task+(d.next_step?'\\nNEXT > '+d.next_step:''):'No active execution.'));"
    )
    html = html.replace(
        "E('intent').textContent=d.goal?'GOAL · ACTIVE':'INTENTS · '+intents.length;",
        "E('intent').textContent=d.plan_active?'PLAN · '+(d.plan_done_count||0)+'/'+(d.plan_step_count||0):(d.goal?'GOAL · ACTIVE':'INTENTS · '+intents.length);"
    )
    return html


from app.api.routes.auron_demo1_plan_execution_coordinator_v21_250 import router as _auron_v21_250_router
router.routes.extend(_auron_v21_250_router.routes)
