from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_execution_admission_gate_v21_257 import (
    _admission,
    _guarded_run,
    command_center as v21_257_command_center,
    dialogue as v21_257_dialogue,
)

router = APIRouter(prefix='/auron/demo1/v21.258', tags=['auron-demo1-execution-policy-controller'])

OBSERVE_MARKERS = ('status', 'zeige', 'check', 'prüfe', 'pruefe', 'what is', 'wie ist', 'was ist')
PLAN_MARKERS = ('plane ', 'plan ', 'erstelle plan', 'nächster schritt', 'naechster schritt', 'strategie', 'roadmap')
EXECUTE_MARKERS = ('führe ', 'fuehre ', 'starte ', 'execute ', 'run ')
APPROVAL_MARKERS = (
    'trade', 'order', 'kaufen', 'verkaufen', 'buy ', 'sell ', 'position', 'lot ', 'mt5',
    'zahlung', 'bezahle', 'überweise', 'ueberweise', 'payment', 'transfer', 'financial',
)
BLOCK_MARKERS = (
    'lösche alles', 'loesche alles', 'delete all', 'disable safety', 'bypass approval',
    'risk brain deaktivieren', 'approval umgehen', 'override safety',
)


def _normalize(text: str) -> str:
    return ' '.join(text.casefold().strip(' .!?').split())


def _policy(req: DialogueRequest) -> dict:
    text = _normalize(req.command)
    admission = _admission(req)

    if any(marker in text for marker in BLOCK_MARKERS):
        mode = 'blocked'
        reason = 'explicit-safety-boundary'
        allowed = False
        approval_required = False
    elif any(marker in text for marker in APPROVAL_MARKERS) and any(marker in text for marker in EXECUTE_MARKERS):
        mode = 'approval-required'
        reason = 'financial-or-high-risk-execution'
        allowed = False
        approval_required = True
    elif any(marker in text for marker in EXECUTE_MARKERS):
        mode = 'low-risk-execute' if admission['allowed'] else 'blocked'
        reason = 'admission-passed' if admission['allowed'] else 'execution-admission-denied'
        allowed = bool(admission['allowed'])
        approval_required = False
    elif any(marker in text for marker in PLAN_MARKERS):
        mode = 'plan'
        reason = 'planning-only'
        allowed = True
        approval_required = False
    else:
        mode = 'observe'
        reason = 'read-or-conversation'
        allowed = True
        approval_required = False

    return {
        'mode': mode,
        'allowed': allowed,
        'reason': reason,
        'approval_required': approval_required,
        'admission': admission,
        'high_risk_autonomy': False,
    }


def _policy_reply(policy: dict) -> str:
    mode = policy['mode']
    if mode == 'approval-required':
        return 'Execution Policy: approval-required. Finanzielle oder High-Risk-Ausführung benötigt menschliche Freigabe.'
    if mode == 'blocked':
        return f"Execution Policy: blocked. Grund: {policy['reason']}."
    if mode == 'low-risk-execute':
        return 'Execution Policy: low-risk-execute. Admission Gate ist freigegeben.'
    if mode == 'plan':
        return 'Execution Policy: plan. Planung ist erlaubt, es wird nichts ausgeführt.'
    return 'Execution Policy: observe. Lesen, prüfen und normale Konversation sind erlaubt.'


def _command(req: DialogueRequest) -> dict | None:
    text = _normalize(req.command)
    if text in {'execution policy', 'policy status', 'zeige execution policy', 'policy check'}:
        policy = _policy(req)
        return {
            'state': 'completed',
            'mode': 'execution-policy-status',
            'reply': _policy_reply(policy),
            'detected_intents': ['execution-policy-controller'],
            'steps': [],
            'approval_required': policy['approval_required'],
            'policy': policy,
        }
    if text in {'starte policy-geprüften queue run', 'starte policy-geprueften queue run', 'run policy guarded queue'}:
        policy = _policy(DialogueRequest(session_id=req.session_id, workspace_id=req.workspace_id, operator_id=req.operator_id, command='run guarded queue'))
        if policy['mode'] != 'low-risk-execute':
            return {
                'state': 'blocked',
                'mode': 'execution-policy-blocked',
                'reply': _policy_reply(policy),
                'detected_intents': ['execution-policy-controller'],
                'steps': [],
                'approval_required': policy['approval_required'],
                'policy': policy,
            }
        result = _guarded_run(req, resilient=False)
        result['policy'] = policy
        result['policy_checked'] = True
        return result
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _command(req)
    if direct is not None:
        return direct

    policy = _policy(req)
    if policy['mode'] == 'approval-required':
        return {
            'state': 'approval-required',
            'mode': 'execution-policy-approval-required',
            'reply': _policy_reply(policy),
            'detected_intents': ['execution-policy-controller'],
            'steps': [],
            'approval_required': True,
            'policy': policy,
        }
    if policy['mode'] == 'blocked':
        return {
            'state': 'blocked',
            'mode': 'execution-policy-blocked',
            'reply': _policy_reply(policy),
            'detected_intents': ['execution-policy-controller'],
            'steps': [],
            'approval_required': False,
            'policy': policy,
        }

    result = v21_257_dialogue(req)
    result['policy'] = policy
    result['policy_checked'] = True
    return result


@router.get('/policy-status')
def policy_status(command: str = 'status', session_id: str = 'policy-status', workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command=command)
    return _policy(req)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_257_command_center()
    html = html.replace('v21.257', 'v21.258')
    html = html.replace('AURON EXECUTION ADMISSION COMMAND CENTER', 'AURON EXECUTION POLICY COMMAND CENTER')
    return html
