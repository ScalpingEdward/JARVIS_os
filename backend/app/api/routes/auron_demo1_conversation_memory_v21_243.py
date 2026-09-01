from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import (
    DialogueRequest,
    _human_summary,
    command_center as v21_242_command_center,
)
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service
from app.models.contracts import ModelRequest
from app.models.router import model_router
from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command

router = APIRouter(prefix='/auron/demo1/v21.243', tags=['auron-demo1-memory'])
CATEGORY = 'auron-conversation'
MAX_CONTEXT_TURNS = 10


def _session_tags(req: DialogueRequest) -> list[str]:
    return [f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}']


def _remember(req: DialogueRequest, role: str, content: str) -> None:
    memory_service.create(MemoryCreate(
        content=content,
        category=CATEGORY,
        priority=MemoryPriority.normal,
        tags=[*_session_tags(req), f'role:{role}'],
    ))


def _history(req: DialogueRequest, limit: int = MAX_CONTEXT_TURNS * 2) -> list[dict[str, str]]:
    required = set(_session_tags(req))
    records = [
        item for item in memory_service.list_all(category=CATEGORY)
        if required.issubset(set(item.tags))
    ]
    records.sort(key=lambda item: item.created_at)
    result: list[dict[str, str]] = []
    for item in records[-limit:]:
        role = 'assistant' if 'role:assistant' in item.tags else 'user'
        result.append({'role': role, 'content': item.content})
    return result


def _conversation_reply(req: DialogueRequest, history: list[dict[str, str]]) -> str:
    text = req.command.lower().strip()
    greetings = ('hallo', 'hi ', 'hey', 'guten morgen', 'guten tag', 'master brano', 'bin hier', 'ich bin da')
    if any(term in text for term in greetings) and len(history) <= 1:
        return 'Willkommen zurück, Master Brano. AURON ist online und bereit. Was möchtest du tun?'

    providers = model_router.available_providers()
    provider = 'openai' if 'openai' in providers else ('anthropic' if 'anthropic' in providers else None)
    if provider:
        transcript = '\n'.join(
            ('Master Brano' if turn['role'] == 'user' else 'AURON') + ': ' + turn['content']
            for turn in history[-MAX_CONTEXT_TURNS * 2:]
        )
        prompt = (
            'Du bist AURON, ein präziser persönlicher AI-Operator. Antworte auf Deutsch kurz, natürlich und direkt. '
            'Nutze den Gesprächskontext, damit Folgefragen verstanden werden. Behaupte niemals Tool-Aktionen, die nicht ausgeführt wurden. '
            'Finanzielle oder andere High-Risk-Aktionen benötigen Freigabe. Nutzername: Master Brano.\n\n'
            'Gesprächskontext:\n' + transcript + '\n\nAURON:'
        )
        try:
            return model_router.generate(ModelRequest(prompt=prompt, task_type='operator_dialogue_context'), provider_name=provider).content
        except Exception:
            pass

    if len(history) > 1:
        previous = next((turn['content'] for turn in reversed(history[:-1]) if turn['role'] == 'user'), None)
        if previous:
            return f'Ich habe den Gesprächskontext behalten. Deine vorherige Anfrage war: „{previous[:180]}“. Für eine freie inhaltliche Antwort muss noch ein AI-Modell verbunden sein.'
    return 'Ich habe dich verstanden. Der Gesprächskontext wird gespeichert; für freie Antworten muss noch ein AI-Modell verbunden sein.'


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    _remember(req, 'user', req.command)
    execution = execute_operator_command(IntentRouteRequest(
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        command=req.command,
        risk_brain_hard_block=req.risk_brain_hard_block,
    ))

    if execution.state == 'unsupported':
        history = _history(req)
        reply = _conversation_reply(req, history)
        _remember(req, 'assistant', reply)
        return {
            'state': 'conversation', 'mode': 'conversation', 'reply': reply,
            'detected_intents': [], 'steps': [], 'approval_required': False,
            'context_turns': len(history) + 1, 'memory_persisted': True,
        }

    reply = _human_summary(execution)
    _remember(req, 'assistant', reply)
    return {
        'state': execution.state, 'mode': 'capability', 'reply': reply,
        'detected_intents': execution.detected_intents,
        'steps': [step.model_dump(mode='json') for step in execution.steps],
        'approval_required': execution.approval_required,
        'context_turns': len(_history(req)), 'memory_persisted': True,
    }


@router.get('/context')
def context(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='context')
    history = _history(req)
    return {'session_id': session_id, 'turns': history, 'count': len(history), 'persistent': True}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_242_command_center()
    html = html.replace('v21.242', 'v21.243')
    html = html.replace('CONVERSATIONAL COMMAND CENTER', 'CONTEXT MEMORY COMMAND CENTER')
    html = html.replace("session_id:'auron-'+Date.now()", "session_id:getSessionId()")
    marker = "const E=id=>document.getElementById(id),safe=x=>String(x??'');"
    replacement = marker + "function getSessionId(){let s=localStorage.getItem('auron-session-id');if(!s){s='auron-'+Date.now()+'-'+Math.random().toString(36).slice(2,9);localStorage.setItem('auron-session-id',s)}return s;}"
    html = html.replace(marker, replacement)
    html = html.replace("E('steps').textContent='STEPS · '+steps.length;", "E('steps').textContent='MEMORY · '+(d.context_turns||0)+' TURNS';")
    return html


# Later AURON versions attach through this already-registered router to keep main.py stable.
from app.api.routes.auron_demo1_long_term_memory_v21_244 import router as _auron_v21_244_router
router.routes.extend(_auron_v21_244_router.routes)
from app.api.routes.auron_demo1_contextual_long_term_memory_v21_245 import router as _auron_v21_245_router
router.routes.extend(_auron_v21_245_router.routes)

# v21.255 is registered directly in main.py (app.include_router), so it is
# deliberately NOT re-merged here anymore -- the previous merge caused every
# v21.255 route to be registered twice (once here, once directly), which
# silently shadowed one of the two copies. See JARVIS_MASTER_PLAN.md
# (route-collision reconciliation) for the full audit.
