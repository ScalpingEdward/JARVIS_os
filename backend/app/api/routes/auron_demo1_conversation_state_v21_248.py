from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_memory_candidates_v21_247 import (
    command_center as v21_247_command_center,
    dialogue as v21_247_dialogue,
)
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.248', tags=['auron-demo1-conversation-state'])
STATE_CATEGORY = 'auron-conversation-state'
STATE_KINDS = ('goal', 'task', 'next-step')


def _scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _records(req: DialogueRequest, kind: str | None = None) -> list:
    required = _scope(req)
    if kind:
        required.add(f'kind:{kind}')
    items = [
        item for item in memory_service.list_all(category=STATE_CATEGORY)
        if required.issubset(set(item.tags))
    ]
    return sorted(items, key=lambda item: item.created_at)


def _current(req: DialogueRequest, kind: str) -> str | None:
    items = _records(req, kind)
    return items[-1].content if items else None


def _set(req: DialogueRequest, kind: str, content: str) -> None:
    for item in _records(req, kind):
        memory_service.delete(item.id)
    memory_service.create(MemoryCreate(
        content=content.strip(),
        category=STATE_CATEGORY,
        priority=MemoryPriority.high,
        tags=[*_scope(req), f'kind:{kind}', 'state:active'],
    ))


def _clear(req: DialogueRequest, kind: str) -> None:
    for item in _records(req, kind):
        memory_service.delete(item.id)


def _state(req: DialogueRequest) -> dict:
    return {
        'goal': _current(req, 'goal'),
        'task': _current(req, 'task'),
        'next_step': _current(req, 'next-step'),
    }


def _extract_after(text: str, prefixes: tuple[str, ...]) -> str | None:
    raw = text.strip()
    lowered = raw.casefold()
    for prefix in prefixes:
        index = lowered.find(prefix)
        if index >= 0:
            value = raw[index + len(prefix):].strip(' :,-.?!')
            return value or None
    return None


def _state_command(req: DialogueRequest) -> dict | None:
    text = req.command.strip()
    lowered = text.casefold().strip(' .!?')

    goal = _extract_after(text, ('aktuelles ziel ist', 'unser ziel ist', 'mein aktuelles ziel ist', 'current goal is'))
    if goal:
        _set(req, 'goal', goal)
        state = _state(req)
        return _response('state-goal-set', f'Aktuelles Ziel gesetzt: {goal}', state)

    task = _extract_after(text, ('wir arbeiten an', 'aktuelle aufgabe ist', 'aktuelle task ist', 'current task is', 'we are working on'))
    if task:
        _set(req, 'task', task)
        state = _state(req)
        return _response('state-task-set', f'Aktueller Fokus gesetzt: {task}', state)

    next_step = _extract_after(text, ('nächster schritt ist', 'naechster schritt ist', 'als nächstes machen wir', 'als naechstes machen wir', 'next step is'))
    if next_step:
        _set(req, 'next-step', next_step)
        state = _state(req)
        return _response('state-next-step-set', f'Nächster Schritt gesetzt: {next_step}', state)

    state = _state(req)
    if any(q in lowered for q in ('woran arbeiten wir', 'was machen wir gerade', 'was ist die aktuelle aufgabe', 'what are we working on')):
        reply = f'Aktueller Fokus: {state["task"]}.' if state['task'] else 'Aktuell ist noch keine konkrete Aufgabe gesetzt.'
        return _response('state-task-read', reply, state)
    if any(q in lowered for q in ('was ist unser ziel', 'was ist mein aktuelles ziel', 'what is our goal', 'what is my current goal')):
        reply = f'Aktuelles Ziel: {state["goal"]}.' if state['goal'] else 'Aktuell ist noch kein Ziel gesetzt.'
        return _response('state-goal-read', reply, state)
    if any(q in lowered for q in ('was kommt als nächstes', 'was kommt als naechstes', 'was ist der nächste schritt', 'was ist der naechste schritt', 'what is next', 'what is the next step')):
        reply = f'Nächster Schritt: {state["next_step"]}.' if state['next_step'] else 'Aktuell ist noch kein nächster Schritt gesetzt.'
        return _response('state-next-step-read', reply, state)
    if any(q in lowered for q in ('zeig arbeitsstatus', 'zeige arbeitsstatus', 'show work state', 'show current state')):
        return _response('state-read', _state_summary(state), state)

    if lowered in {'ziel erledigt', 'ziel abgeschlossen', 'clear goal'}:
        _clear(req, 'goal')
        return _response('state-goal-cleared', 'Aktuelles Ziel wurde abgeschlossen.', _state(req))
    if lowered in {'aufgabe erledigt', 'task erledigt', 'aufgabe abgeschlossen', 'clear task'}:
        _clear(req, 'task')
        return _response('state-task-cleared', 'Aktuelle Aufgabe wurde abgeschlossen.', _state(req))
    if lowered in {'schritt erledigt', 'nächster schritt erledigt', 'naechster schritt erledigt', 'clear next step'}:
        _clear(req, 'next-step')
        return _response('state-next-step-cleared', 'Der nächste Schritt wurde abgeschlossen.', _state(req))
    return None


def _state_summary(state: dict) -> str:
    goal = state['goal'] or 'nicht gesetzt'
    task = state['task'] or 'nicht gesetzt'
    next_step = state['next_step'] or 'nicht gesetzt'
    return f'Ziel: {goal}. Aktueller Fokus: {task}. Nächster Schritt: {next_step}.'


def _response(mode: str, reply: str, state: dict) -> dict:
    return {
        'state': 'completed',
        'mode': mode,
        'reply': reply,
        'detected_intents': ['conversation-state'],
        'steps': [],
        'approval_required': False,
        'conversation_state': state,
        'goal': state['goal'],
        'current_task': state['task'],
        'next_step': state['next_step'],
    }


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _state_command(req)
    if direct is not None:
        return direct
    result = v21_247_dialogue(req)
    state = _state(req)
    result['conversation_state'] = state
    result['goal'] = state['goal']
    result['current_task'] = state['task']
    result['next_step'] = state['next_step']
    return result


@router.get('/state')
def conversation_state(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='state-view')
    state = _state(req)
    return {'active': any(state.values()), **state}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_247_command_center()
    html = html.replace('v21.247', 'v21.248')
    html = html.replace('MEMORY LEARNING COMMAND CENTER', 'MISSION STATE COMMAND CENTER')
    html = html.replace(
        "E('processes').textContent=steps.length?steps.map((s,i)=>(i+1)+'. '+(s.intent||s.capability)+' ['+s.state+']').join('\\n'):'No active execution.';",
        "E('processes').textContent=steps.length?steps.map((s,i)=>(i+1)+'. '+(s.intent||s.capability)+' ['+s.state+']').join('\\n'):(d.current_task?'FOCUS > '+d.current_task+(d.next_step?'\\nNEXT > '+d.next_step:''):'No active execution.');"
    )
    html = html.replace(
        "E('intent').textContent='INTENTS · '+intents.length;",
        "E('intent').textContent=d.goal?'GOAL · ACTIVE':'INTENTS · '+intents.length;"
    )
    return html
