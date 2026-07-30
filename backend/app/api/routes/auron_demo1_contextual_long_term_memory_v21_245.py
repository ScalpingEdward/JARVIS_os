from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest, _human_summary
from app.api.routes.auron_demo1_conversation_memory_v21_243 import _history, _remember
from app.api.routes.auron_demo1_long_term_memory_v21_244 import (
    _facts,
    _memory_command,
    command_center as v21_244_command_center,
)
from app.models.contracts import ModelRequest
from app.models.router import model_router
from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command

router = APIRouter(prefix='/auron/demo1/v21.245', tags=['auron-demo1-contextual-memory'])
MAX_FACTS_IN_PROMPT = 12
MAX_CONTEXT_TURNS = 10


def _facts_for_prompt(req: DialogueRequest) -> list[str]:
    return [item.content for item in _facts(req)[-MAX_FACTS_IN_PROMPT:]]


def _contextual_reply(req: DialogueRequest, history: list[dict[str, str]], facts: list[str]) -> str:
    providers = model_router.available_providers()
    provider = 'openai' if 'openai' in providers else ('anthropic' if 'anthropic' in providers else None)

    if provider:
        transcript = '\n'.join(
            ('Master Brano' if turn['role'] == 'user' else 'AURON') + ': ' + turn['content']
            for turn in history[-MAX_CONTEXT_TURNS * 2:]
        )
        memory_block = '\n'.join(f'- {fact}' for fact in facts) if facts else '- keine ausdrücklich gespeicherten Fakten'
        prompt = (
            'Du bist AURON, ein präziser persönlicher AI-Operator. Antworte auf Deutsch kurz, natürlich und direkt. '
            'Nutze gespeichertes Langzeitwissen nur dann, wenn es für die aktuelle Aussage oder Frage relevant ist. '
            'Erfinde keine Erinnerungen. Behaupte niemals Tool-Aktionen, die nicht ausgeführt wurden. '
            'Finanzielle oder andere High-Risk-Aktionen benötigen Freigabe. Nutzername: Master Brano.\n\n'
            'Langzeitwissen über den Nutzer:\n' + memory_block + '\n\n'
            'Aktueller Gesprächskontext:\n' + transcript + '\n\nAURON:'
        )
        try:
            return model_router.generate(
                ModelRequest(prompt=prompt, task_type='operator_dialogue_contextual_memory'),
                provider_name=provider,
            ).content
        except Exception:
            pass

    if facts:
        latest = facts[-3:]
        return (
            'Ich habe deinen Gesprächskontext und mein Langzeitwissen geladen. '
            'Aktuell relevante gespeicherte Fakten sind: ' + '; '.join(latest) + '. '
            'Für eine freie, natürlich formulierte Antwort muss noch ein AI-Modell verbunden sein.'
        )
    if len(history) > 1:
        previous = next((turn['content'] for turn in reversed(history[:-1]) if turn['role'] == 'user'), None)
        if previous:
            return f'Ich habe den Gesprächskontext behalten. Deine vorherige Anfrage war: „{previous[:180]}“.'
    return 'Ich habe dich verstanden. Gesprächskontext und Langzeitmemory sind aktiv.'


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    memory_result = _memory_command(req)
    if memory_result is not None:
        memory_result['contextual_memory_active'] = True
        return memory_result

    _remember(req, 'user', req.command)
    execution = execute_operator_command(IntentRouteRequest(
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        command=req.command,
        risk_brain_hard_block=req.risk_brain_hard_block,
    ))

    facts = _facts_for_prompt(req)
    if execution.state == 'unsupported':
        history = _history(req)
        reply = _contextual_reply(req, history, facts)
        _remember(req, 'assistant', reply)
        return {
            'state': 'conversation', 'mode': 'conversation', 'reply': reply,
            'detected_intents': [], 'steps': [], 'approval_required': False,
            'context_turns': len(history) + 1, 'memory_persisted': True,
            'long_term_memory_count': len(_facts(req)),
            'contextual_memory_active': True,
            'contextual_facts_used': len(facts),
        }

    reply = _human_summary(execution)
    _remember(req, 'assistant', reply)
    return {
        'state': execution.state, 'mode': 'capability', 'reply': reply,
        'detected_intents': execution.detected_intents,
        'steps': [step.model_dump(mode='json') for step in execution.steps],
        'approval_required': execution.approval_required,
        'context_turns': len(_history(req)), 'memory_persisted': True,
        'long_term_memory_count': len(_facts(req)),
        'contextual_memory_active': True,
        'contextual_facts_used': len(facts),
    }


@router.get('/memory-context')
def memory_context(workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id='memory-context-view', workspace_id=workspace_id, operator_id=operator_id, command='memory-context-view')
    facts = _facts_for_prompt(req)
    return {
        'active': True,
        'long_term_memory_count': len(_facts(req)),
        'facts_available_for_context': facts,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_244_command_center()
    html = html.replace('v21.244', 'v21.245')
    html = html.replace('LONG-TERM MEMORY COMMAND CENTER', 'CONTEXTUAL MEMORY COMMAND CENTER')
    html = html.replace(
        "E('steps').textContent='MEMORY · '+(d.context_turns||0)+' TURNS';",
        "E('steps').textContent='MEMORY · '+(d.context_turns||0)+' CTX · '+(d.long_term_memory_count||0)+' FACTS';",
    )
    return html


from app.api.routes.auron_demo1_smart_memory_retrieval_v21_246 import router as _auron_v21_246_router
router.routes.extend(_auron_v21_246_router.routes)
