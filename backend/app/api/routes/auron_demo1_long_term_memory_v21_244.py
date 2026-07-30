from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_conversation_memory_v21_243 import (
    command_center as v21_243_command_center,
    dialogue as v21_243_dialogue,
)
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.244', tags=['auron-demo1-long-term-memory'])
CATEGORY = 'auron-long-term'


def _scope(req: DialogueRequest) -> set[str]:
    return {f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _facts(req: DialogueRequest) -> list:
    required = _scope(req)
    items = [item for item in memory_service.list_all(category=CATEGORY) if required.issubset(set(item.tags))]
    return sorted(items, key=lambda item: item.created_at)


def _extract_after(text: str, prefixes: tuple[str, ...]) -> str | None:
    lowered = text.lower().strip()
    for prefix in prefixes:
        index = lowered.find(prefix)
        if index >= 0:
            value = text[index + len(prefix):].strip(' :,-.?!')
            return value or None
    return None


def _memory_command(req: DialogueRequest) -> dict | None:
    command = req.command.strip()
    lowered = command.lower()

    remember = _extract_after(command, ('merk dir', 'merke dir', 'remember that', 'remember:'))
    if remember:
        record = memory_service.create(MemoryCreate(
            content=remember,
            category=CATEGORY,
            priority=MemoryPriority.high,
            tags=[*_scope(req), 'source:explicit-operator-memory'],
        ))
        return {
            'state': 'completed', 'mode': 'memory-write',
            'reply': f'Gemerkte Information gespeichert: {remember}',
            'detected_intents': ['long-term-memory-write'], 'steps': [],
            'approval_required': False, 'memory_persisted': True,
            'long_term_memory_count': len(_facts(req)), 'memory_id': str(record.id),
        }

    if any(term in lowered for term in ('was hast du dir gemerkt', 'was weißt du über mich', 'was weisst du über mich', 'what do you remember')):
        facts = _facts(req)
        if not facts:
            reply = 'Ich habe noch keine ausdrücklich gespeicherten Langzeitinformationen.'
        else:
            latest = facts[-8:]
            reply = 'Ich habe mir gemerkt: ' + '; '.join(item.content for item in latest)
        return {
            'state': 'completed', 'mode': 'memory-read', 'reply': reply,
            'detected_intents': ['long-term-memory-read'], 'steps': [],
            'approval_required': False, 'memory_persisted': True,
            'long_term_memory_count': len(facts),
        }

    forget = _extract_after(command, ('vergiss', 'forget'))
    if forget:
        if forget.lower() in {'alles', 'everything', 'all'}:
            return {
                'state': 'confirmation-required', 'mode': 'memory-delete',
                'reply': 'Ich lösche nicht pauschal alle Langzeitinformationen. Nenne bitte konkret, was ich vergessen soll.',
                'detected_intents': ['long-term-memory-delete'], 'steps': [],
                'approval_required': False, 'memory_persisted': True,
                'long_term_memory_count': len(_facts(req)),
            }
        matches = [item for item in _facts(req) if forget.casefold() in item.content.casefold()]
        for item in matches:
            memory_service.delete(item.id)
        reply = f'{len(matches)} passende Langzeitinformation(en) vergessen.' if matches else 'Dazu habe ich keine passende Langzeitinformation gefunden.'
        return {
            'state': 'completed', 'mode': 'memory-delete', 'reply': reply,
            'detected_intents': ['long-term-memory-delete'], 'steps': [],
            'approval_required': False, 'memory_persisted': True,
            'long_term_memory_count': len(_facts(req)),
        }
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    memory_result = _memory_command(req)
    if memory_result is not None:
        return memory_result
    result = v21_243_dialogue(req)
    result['long_term_memory_count'] = len(_facts(req))
    return result


@router.get('/long-term-memory')
def long_term_memory(workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id='memory-view', workspace_id=workspace_id, operator_id=operator_id, command='memory-view')
    facts = _facts(req)
    return {'count': len(facts), 'items': [{'id': str(item.id), 'content': item.content} for item in facts]}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_243_command_center()
    html = html.replace('v21.243', 'v21.244')
    html = html.replace('CONTEXT MEMORY COMMAND CENTER', 'LONG-TERM MEMORY COMMAND CENTER')
    capture = "const c=E('command').value.trim();if(!c)return;"
    html = html.replace(capture, capture + "E('command').value='';E('command').focus();")
    return html
