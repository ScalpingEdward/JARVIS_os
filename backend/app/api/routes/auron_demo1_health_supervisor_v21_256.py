from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_provider_brain_v21_254 import brain_status
from app.api.routes.auron_demo1_retry_recovery_v21_255 import (
    MAX_RETRIES,
    _recovery,
    command_center as v21_255_command_center,
    dialogue as v21_255_dialogue,
)
from app.api.routes.auron_demo1_runner_checkpoints_v21_253 import _status

router = APIRouter(prefix='/auron/demo1/v21.256', tags=['auron-demo1-health-supervisor'])


def _health(req: DialogueRequest) -> dict:
    brain = brain_status()
    runner = _status(req)
    recovery = _recovery(req)

    providers = brain.get('available_providers') or []
    runner_paused = bool(runner.get('runner_paused'))
    retry_count = int(recovery.get('retry_count') or 0)
    stop_reason = recovery.get('last_stop_reason')

    checks = {
        'brain': {
            'state': 'ready' if providers else 'degraded',
            'providers': providers,
            'preferred_provider': brain.get('preferred_provider'),
        },
        'runner': {
            'state': 'paused' if runner_paused else 'ready',
            'paused': runner_paused,
            'queue_completed_count': int(runner.get('queue_completed_count') or 0),
            'queue_ready_count': int(runner.get('queue_ready_count') or 0),
        },
        'recovery': {
            'state': 'degraded' if retry_count else 'ready',
            'retry_count': retry_count,
            'max_retries': MAX_RETRIES,
            'retryable': bool(recovery.get('retryable')),
            'last_stop_reason': stop_reason,
        },
        'governance': {
            'state': 'ready',
            'high_risk_approval_required': True,
            'risk_brain_authoritative': True,
        },
    }

    score = 100
    if not providers:
        score -= 20
    if runner_paused:
        score -= 10
    score -= min(retry_count, MAX_RETRIES) * 15
    if stop_reason in {'blocked', 'approval-required'}:
        score -= 5
    score = max(0, score)

    if score >= 90:
        overall = 'healthy'
    elif score >= 60:
        overall = 'degraded'
    else:
        overall = 'attention-required'

    return {
        'overall': overall,
        'score': score,
        'checks': checks,
        'safe_to_run_low_risk_queue': overall != 'attention-required' and not runner_paused,
        'high_risk_autonomy': False,
    }


def _health_reply(health: dict) -> str:
    brain_state = health['checks']['brain']['state']
    runner_state = health['checks']['runner']['state']
    retry_count = health['checks']['recovery']['retry_count']
    return (
        f"System Health: {health['overall']} ({health['score']}/100). "
        f"Brain: {brain_state}. Runner: {runner_state}. Retries: {retry_count}/{MAX_RETRIES}."
    )


def _command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())
    if normalized in {
        'system health', 'health status', 'auron health', 'systemstatus',
        'zeige system health', 'zeige health status', 'wie ist dein status',
    }:
        health = _health(req)
        return {
            'state': 'completed',
            'mode': 'health-supervisor',
            'reply': _health_reply(health),
            'detected_intents': ['health-supervisor'],
            'steps': [],
            'approval_required': False,
            'health': health,
        }
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _command(req)
    if direct is not None:
        return direct
    result = v21_255_dialogue(req)
    result['health'] = _health(req)
    return result


@router.get('/health-status')
def health_status(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(
        session_id=session_id,
        workspace_id=workspace_id,
        operator_id=operator_id,
        command='health-status',
    )
    return _health(req)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_255_command_center()
    html = html.replace('v21.255', 'v21.256')
    html = html.replace('RESILIENT AURON COMMAND CENTER', 'AURON HEALTH SUPERVISOR COMMAND CENTER')
    html = html.replace(
        "E('channel').textContent=d.brain_provider?'BRAIN · '+d.brain_provider.toUpperCase():'VOICE · '+(window.speechSynthesis?'READY':'OFF');",
        "E('channel').textContent=d.health?'HEALTH · '+String(d.health.score||0)+'/100':(d.brain_provider?'BRAIN · '+d.brain_provider.toUpperCase():'VOICE · '+(window.speechSynthesis?'READY':'OFF'));",
    )
    return html
