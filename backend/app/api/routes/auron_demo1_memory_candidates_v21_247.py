from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_long_term_memory_v21_244 import CATEGORY as LONG_TERM_CATEGORY, _facts, _scope
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.247', tags=['auron-demo1-memory-candidates'])
CANDIDATE_CATEGORY = 'auron-memory-candidate'


def _candidate_scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}', 'state:pending'}


def _pending_candidates(req: DialogueRequest) -> list:
    required = _candidate_scope(req)
    items = [item for item in memory_service.list_all(category=CANDIDATE_CATEGORY) if required.issubset(set(item.tags))]
    return sorted(items, key=lambda item: item.created_at)


def _clear_pending(req: DialogueRequest) -> None:
    for item in _pending_candidates(req):
        memory_service.delete(item.id)


def _candidate_from_text(text: str) -> str | None:
    raw = text.strip()
    lowered = raw.casefold()
    if len(raw) < 12 or len(raw) > 500:
        return None
    markers = ('ich bevorzuge ', 'ich mag ', 'ich möchte ', 'ich moechte ', 'mein ziel ist ', 'mein plan ist ', 'meine priorität ist ', 'meine prioritaet ist ', 'mein bevorzugter ', 'meine bevorzugte ', 'für mich ist wichtig ', 'fuer mich ist wichtig ', 'i prefer ', 'i like ', 'my goal is ', 'my plan is ', 'important to me is ')
    if any(marker in lowered for marker in markers):
        return raw.strip(' .!?')
    return None


def _confirmation_action(text: str) -> str | None:
    normalized = ' '.join(text.casefold().replace(',', ' ').strip(' .!?').split())
    if normalized in {'ja merk dir das','merk dir das','ja speichern','ja speicher das','remember it','yes remember it'}:
        return 'confirm'
    if normalized in {'nein','nein nicht merken','nicht merken','vergiss es','no','do not remember it',"don't remember it"}:
        return 'reject'
    return None


def _handle_confirmation(req: DialogueRequest) -> dict | None:
    action = _confirmation_action(req.command)
    if action is None:
        return None
    pending = _pending_candidates(req)
    if not pending:
        return {'state':'completed','mode':'memory-candidate','reply':'Es gibt aktuell keine offene Erinnerung zum Bestätigen.','detected_intents':['memory-candidate-confirmation'],'steps':[],'approval_required':False,'memory_persisted':True,'memory_candidate_pending':False}
    content = pending[-1].content
    _clear_pending(req)
    if action == 'reject':
        return {'state':'completed','mode':'memory-candidate-rejected','reply':'Okay, das speichere ich nicht als Langzeiterinnerung.','detected_intents':['memory-candidate-reject'],'steps':[],'approval_required':False,'memory_persisted':True,'memory_candidate_pending':False}
    record = memory_service.create(MemoryCreate(content=content, category=LONG_TERM_CATEGORY, priority=MemoryPriority.high, tags=[*_scope(req), 'source:confirmed-conversation-memory']))
    return {'state':'completed','mode':'memory-candidate-confirmed','reply':f'Ja. Ich habe mir das dauerhaft gemerkt: {content}','detected_intents':['memory-candidate-confirm'],'steps':[],'approval_required':False,'memory_persisted':True,'memory_candidate_pending':False,'memory_id':str(record.id),'long_term_memory_count':len(_facts(req))}


def _store_candidate(req: DialogueRequest, content: str) -> None:
    _clear_pending(req)
    memory_service.create(MemoryCreate(content=content, category=CANDIDATE_CATEGORY, priority=MemoryPriority.normal, tags=list(_candidate_scope(req))))


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    from app.api.routes.auron_demo1_smart_memory_retrieval_v21_246 import dialogue as v21_246_dialogue

    confirmation = _handle_confirmation(req)
    if confirmation is not None:
        return confirmation

    candidate = _candidate_from_text(req.command)
    result = v21_246_dialogue(req)

    if result.get('state') in {'blocked', 'approval-required'}:
        candidate = None

    if candidate:
        _store_candidate(req, candidate)
        result['memory_candidate_pending'] = True
        result['memory_candidate'] = candidate
        result['reply'] = result['reply'].rstrip() + ' Das klingt nach etwas, das länger wichtig sein könnte. Soll ich mir das merken?'
    else:
        result['memory_candidate_pending'] = bool(_pending_candidates(req))
    return result


@router.get('/memory-candidate')
def memory_candidate(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='candidate-view')
    pending = _pending_candidates(req)
    return {'pending': bool(pending), 'candidate': pending[-1].content if pending else None, 'count': len(pending)}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_smart_memory_retrieval_v21_246 import command_center as v21_246_command_center

    html = v21_246_command_center()
    html = html.replace('v21.246', 'v21.247')
    html = html.replace('SMART MEMORY COMMAND CENTER', 'MEMORY LEARNING COMMAND CENTER')
    html = html.replace("E('approval').textContent='APPROVAL · '+(d.approval_required?'YES':'NO');", "E('approval').textContent=d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO');")
    return html


from app.api.routes.auron_demo1_conversation_state_v21_248 import router as _auron_v21_248_router
router.routes.extend(_auron_v21_248_router.routes)
