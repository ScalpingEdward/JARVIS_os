from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_health_supervisor_v21_256 import (
    _health,
    command_center as v21_256_command_center,
    dialogue as v21_256_dialogue,
)
from app.api.routes.auron_demo1_retry_recovery_v21_255 import _run_with_recovery

router = APIRouter(prefix='/auron/demo1/v21.257', tags=['auron-demo1-execution-admission-gate'])
MIN_SAFE_SCORE = 60


def _admission(req: DialogueRequest) -> dict:
    health = _health(req)
    score = int(health.get('score') or 0)
    overall = health.get('overall') or 'attention-required'
    runner_paused = bool(health.get('checks', {}).get('runner', {}).get('paused'))
    recovery = health.get('checks', {}).get('recovery', {})
    retry_count = int(recovery.get('retry_count') or 0)

    reasons: list[str] = []
    if score < MIN_SAFE_SCORE:
        reasons.append(f'health-score-below-{MIN_SAFE_SCORE}')
    if overall == 'attention-required':
        reasons.append('health-attention-required')
    if runner_paused:
        reasons.append('runner-paused')
    if retry_count >= int(recovery.get('max_retries') or 2):
        reasons.append('retry-limit-reached')

    allowed = not reasons and bool(health.get('safe_to_run_low_risk_queue'))
    return {
        'allowed': allowed,
        'classification': 'admitted' if allowed else 'denied',
        'health_score': score,
        'health_state': overall,
        'reasons': reasons,
        'low_risk_only': True,
        'high_risk_autonomy': False,
    }


def _admission_reply(admission: dict) -> str:
    if admission['allowed']:
        return (
            f"Execution Gate: admitted. Health {admission['health_score']}/100. "
            'Sichere Low-Risk-Queue-Ausführung ist zugelassen.'
        )
    reasons = ', '.join(admission['reasons']) or 'health-gate-denied'
    return (
        f"Execution Gate: denied. Health {admission['health_score']}/100. "
        f"Grund: {reasons}."
    )


def _guarded_run(req: DialogueRequest, resilient: bool) -> dict:
    admission = _admission(req)
    if not admission['allowed']:
        return {
            'state': 'blocked',
            'mode': 'execution-admission-denied',
            'reply': _admission_reply(admission),
            'detected_intents': ['execution-admission-gate'],
            'steps': [],
            'approval_required': False,
            'admission': admission,
        }

    result = _run_with_recovery(req, allow_retry=resilient)
    result['admission'] = admission
    result['admission_checked'] = True
    return result


def _command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())

    if normalized in {
        'execution gate', 'execution status', 'admission status',
        'darfst du ausführen', 'darfst du ausfuehren', 'kannst du ausführen', 'kannst du ausfuehren',
        'zeige execution gate', 'zeige admission status',
    }:
        admission = _admission(req)
        return {
            'state': 'completed',
            'mode': 'execution-admission-status',
            'reply': _admission_reply(admission),
            'detected_intents': ['execution-admission-gate'],
            'steps': [],
            'approval_required': False,
            'admission': admission,
        }

    if normalized in {
        'starte geprüften queue run', 'starte geprueften queue run',
        'führe geprüfte queue aus', 'fuehre gepruefte queue aus',
        'run admitted queue', 'run guarded queue',
    }:
        return _guarded_run(req, resilient=False)

    if normalized in {
        'starte resilienten geprüften queue run', 'starte resilienten geprueften queue run',
        'run resilient admitted queue', 'run resilient guarded queue',
    }:
        return _guarded_run(req, resilient=True)

    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _command(req)
    if direct is not None:
        return direct
    result = v21_256_dialogue(req)
    result['admission'] = _admission(req)
    return result


@router.get('/admission-status')
def admission_status(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(
        session_id=session_id,
        workspace_id=workspace_id,
        operator_id=operator_id,
        command='admission-status',
    )
    return _admission(req)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_256_command_center()
    html = html.replace('v21.256', 'v21.257')
    html = html.replace('AURON HEALTH SUPERVISOR COMMAND CENTER', 'AURON EXECUTION ADMISSION COMMAND CENTER')
    old_channel = "E('channel').textContent=d.health?'HEALTH · '+String(d.health.score||0)+'/100':(d.brain_provider?'BRAIN · '+d.brain_provider.toUpperCase():'VOICE · '+(window.speechSynthesis?'READY':'OFF'));"
    new_channel = "E('channel').textContent=d.admission?(d.admission.allowed?'GATE · ADMITTED':'GATE · DENIED'):(d.health?'HEALTH · '+String(d.health.score||0)+'/100':(d.brain_provider?'BRAIN · '+d.brain_provider.toUpperCase():'VOICE · '+(window.speechSynthesis?'READY':'OFF')));"
    html = html.replace(old_channel, new_channel)
    return html
