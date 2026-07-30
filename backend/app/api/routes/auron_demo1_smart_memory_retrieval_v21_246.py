import re
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest, _human_summary
from app.models.contracts import ModelRequest
from app.models.router import model_router
from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command

router = APIRouter(prefix='/auron/demo1/v21.246', tags=['auron-demo1-smart-memory'])
MAX_RETRIEVED_FACTS = 6
MAX_CONTEXT_TURNS = 10
STOPWORDS = {
    'auron','der','die','das','den','dem','des','ein','eine','einen','einem','einer','und','oder','aber','ist','sind','war','was','wie','wer','wo','wann','ich','du','mir','mich','mein','meine','meinen','meinem','meiner','zu','zum','zur','von','für','mit','auf','in','im','an','am','the','a','an','and','or','is','are','was','what','how','my','me','you','to','for','with','about'
}


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r'[a-zA-Z0-9ÄÖÜäöüß_-]{2,}', text.casefold())
        if token not in STOPWORDS
    }


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _score_fact(query: str, item) -> float:
    q = _tokens(query)
    f = _tokens(item.content)
    if not q or not f:
        lexical = 0.0
    else:
        overlap = len(q & f)
        lexical = overlap / max(1, len(q))
        if query.casefold() in item.content.casefold() or item.content.casefold() in query.casefold():
            lexical += 1.0

    created_at = _utc_datetime(item.created_at)
    age_days = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 86400.0)
    recency = 1.0 / (1.0 + age_days / 30.0)
    priority = float(getattr(item.priority, 'value', item.priority)) / 4.0
    return lexical * 5.0 + priority * 0.75 + recency * 0.25


def _retrieve_facts(req: DialogueRequest, limit: int = MAX_RETRIEVED_FACTS) -> list[dict]:
    from app.api.routes.auron_demo1_long_term_memory_v21_244 import _facts

    ranked = [(item, _score_fact(req.command, item)) for item in _facts(req)]
    ranked.sort(key=lambda pair: (pair[1], _utc_datetime(pair[0].created_at).timestamp()), reverse=True)
    selected = [pair for pair in ranked if pair[1] > 0.2][:limit]
    if not selected and ranked:
        selected = ranked[:min(2, limit)]
    return [
        {'id': str(item.id), 'content': item.content, 'score': round(score, 4)}
        for item, score in selected
    ]


def _reply(req: DialogueRequest, history: list[dict[str, str]], retrieved: list[dict]) -> str:
    providers = model_router.available_providers()
    provider = 'openai' if 'openai' in providers else ('anthropic' if 'anthropic' in providers else None)
    if provider:
        transcript = '\n'.join(
            ('Master Brano' if turn['role'] == 'user' else 'AURON') + ': ' + turn['content']
            for turn in history[-MAX_CONTEXT_TURNS * 2:]
        )
        memory_block = '\n'.join(f"- {item['content']}" for item in retrieved) or '- keine relevante Erinnerung gefunden'
        prompt = (
            'Du bist AURON, ein präziser persönlicher AI-Operator. Antworte auf Deutsch kurz, natürlich und direkt. '
            'Die folgenden Erinnerungen wurden nach Relevanz zur aktuellen Anfrage ausgewählt. Nutze nur passende Fakten, erfinde nichts und erwähne Memory nicht unnötig. '
            'Behaupte niemals Tool-Aktionen, die nicht ausgeführt wurden. Finanzielle oder andere High-Risk-Aktionen benötigen Freigabe.\n\n'
            'Relevante Langzeit-Erinnerungen:\n' + memory_block + '\n\n'
            'Gesprächskontext:\n' + transcript + '\n\nAURON:'
        )
        try:
            return model_router.generate(
                ModelRequest(prompt=prompt, task_type='operator_dialogue_ranked_memory'),
                provider_name=provider,
            ).content
        except Exception:
            pass

    if retrieved:
        return 'Ich habe die passendsten Erinnerungen geladen: ' + '; '.join(item['content'] for item in retrieved[:3]) + '.'
    if len(history) > 1:
        previous = next((turn['content'] for turn in reversed(history[:-1]) if turn['role'] == 'user'), None)
        if previous:
            return f'Ich habe den Gesprächskontext behalten. Deine vorherige Anfrage war: „{previous[:180]}“.'
    return 'Ich habe dich verstanden. Es wurde keine relevante Langzeiterinnerung gefunden.'


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    from app.api.routes.auron_demo1_conversation_memory_v21_243 import _history, _remember
    from app.api.routes.auron_demo1_long_term_memory_v21_244 import _facts, _memory_command

    memory_result = _memory_command(req)
    if memory_result is not None:
        memory_result['smart_memory_retrieval'] = True
        memory_result['retrieved_fact_count'] = 0
        return memory_result

    _remember(req, 'user', req.command)
    execution = execute_operator_command(IntentRouteRequest(
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        command=req.command,
        risk_brain_hard_block=req.risk_brain_hard_block,
    ))
    retrieved = _retrieve_facts(req)

    if execution.state == 'unsupported':
        history = _history(req)
        reply = _reply(req, history, retrieved)
        _remember(req, 'assistant', reply)
        return {
            'state': 'conversation', 'mode': 'conversation', 'reply': reply,
            'detected_intents': [], 'steps': [], 'approval_required': False,
            'context_turns': len(history) + 1, 'memory_persisted': True,
            'long_term_memory_count': len(_facts(req)),
            'smart_memory_retrieval': True,
            'retrieved_fact_count': len(retrieved),
            'retrieved_facts': retrieved,
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
        'smart_memory_retrieval': True,
        'retrieved_fact_count': len(retrieved),
        'retrieved_facts': retrieved,
    }


@router.get('/memory-retrieval')
def memory_retrieval(q: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id='memory-retrieval-view', workspace_id=workspace_id, operator_id=operator_id, command=q)
    retrieved = _retrieve_facts(req)
    return {'query': q, 'count': len(retrieved), 'items': retrieved, 'smart_memory_retrieval': True}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_contextual_long_term_memory_v21_245 import command_center as v21_245_command_center

    html = v21_245_command_center()
    html = html.replace('v21.245', 'v21.246')
    html = html.replace('CONTEXTUAL MEMORY COMMAND CENTER', 'SMART MEMORY COMMAND CENTER')
    html = html.replace(
        "E('steps').textContent='MEMORY · '+(d.context_turns||0)+' CTX · '+(d.long_term_memory_count||0)+' FACTS';",
        "E('steps').textContent='MEMORY · '+(d.context_turns||0)+' CTX · '+(d.retrieved_fact_count||0)+' REL';",
    )
    return html


from app.api.routes.auron_demo1_memory_candidates_v21_247 import router as _auron_v21_247_router
router.routes.extend(_auron_v21_247_router.routes)
