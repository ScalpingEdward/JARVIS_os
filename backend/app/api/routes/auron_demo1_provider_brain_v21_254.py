from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_runner_checkpoints_v21_253 import (
    command_center as v21_253_command_center,
    dialogue as v21_253_dialogue,
)
from app.models.contracts import ModelRequest
from app.models.router import model_router

router = APIRouter(prefix='/auron/demo1/v21.254', tags=['auron-demo1-provider-brain'])


def _provider_order() -> list[str]:
    available = set(model_router.available_providers())
    return [name for name in ('openai', 'anthropic') if name in available]


def _brain_context(result: dict) -> str:
    state = result.get('conversation_state') or {}
    goal = result.get('goal') or state.get('goal')
    task = result.get('current_task') or state.get('task')
    next_step = result.get('next_step') or state.get('next_step')
    plan_current = result.get('plan_current_step')
    queue_ready = result.get('queue_ready_item') or {}
    checkpoint = result.get('runner_checkpoint') or {}
    memories = result.get('retrieved_facts') or result.get('relevant_memories') or []

    lines = [
        f'Aktuelles Ziel: {goal or "nicht gesetzt"}',
        f'Aktueller Fokus: {task or "nicht gesetzt"}',
        f'Nächster Schritt: {next_step or "nicht gesetzt"}',
        f'Aktueller Planschritt: {plan_current or "nicht gesetzt"}',
        f'Bereiter Queue-Schritt: {queue_ready.get("content") or "keiner"}',
        f'Runner pausiert: {bool(result.get("runner_paused"))}',
        f'Checkpoint: {checkpoint.get("content") or "keiner"}',
    ]
    if memories:
        rendered = []
        for item in memories[:6]:
            if isinstance(item, dict):
                rendered.append(str(item.get('content') or item.get('text') or item))
            else:
                rendered.append(str(item))
        lines.append('Relevante Erinnerungen: ' + ' | '.join(rendered))
    return '\n'.join(lines)


def _provider_reply(req: DialogueRequest, result: dict) -> tuple[str | None, str | None]:
    providers = _provider_order()
    if not providers:
        return None, None

    prompt = (
        'Du bist AURON, der persönliche AI-Operator von Master Brano. '
        'Sprich natürlich, präzise und direkt auf Deutsch. Du bist kein starrer Command-Bot. '
        'Nutze den bereitgestellten Arbeits- und Memory-Kontext, wenn er relevant ist. '
        'Behaupte niemals, eine Tool-Aktion ausgeführt zu haben, wenn das System sie nicht wirklich ausgeführt hat. '
        'Finanzielle, privilegierte oder andere High-Risk-Aktionen benötigen weiterhin explizite Freigabe und die bestehende Governance. '
        'Wenn der Nutzer normal redet oder fragt, antworte normal wie ein leistungsfähiger AI-Assistent. '
        'Wenn der Kontext keine Antwort enthält, darfst du allgemeines Modellwissen verwenden.\n\n'
        'AURON-KONTEXT:\n' + _brain_context(result) + '\n\n'
        'NUTZER:\n' + req.command
    )

    for provider in providers:
        try:
            response = model_router.generate(ModelRequest(prompt=prompt, task_type='auron_operator_dialogue'), provider_name=provider)
            if response.content and response.content.strip():
                return response.content.strip(), provider
        except Exception:
            continue
    return None, None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    result = v21_253_dialogue(req)

    # Operational/capability modes stay deterministic and governed. Only ordinary
    # conversation is handed to the configured frontier-model provider.
    if result.get('mode') == 'conversation' and result.get('state') not in {'blocked', 'approval-required'}:
        reply, provider = _provider_reply(req, result)
        if reply:
            result['reply'] = reply
            result['brain_provider'] = provider
            result['brain_mode'] = 'provider-native'
        else:
            result['brain_provider'] = None
            result['brain_mode'] = 'local-fallback'
    else:
        result['brain_provider'] = None
        result['brain_mode'] = 'governed-capability'

    result['available_brain_providers'] = _provider_order()
    return result


@router.get('/brain-status')
def brain_status() -> dict:
    providers = _provider_order()
    return {
        'provider_native_conversation': bool(providers),
        'available_providers': providers,
        'preferred_provider': providers[0] if providers else None,
        'fallback_provider': providers[1] if len(providers) > 1 else None,
        'operational_commands_governed': True,
        'high_risk_approval_required': True,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_253_command_center()
    html = html.replace('v21.253', 'v21.254')
    html = html.replace('CHECKPOINTED QUEUE RUNNER COMMAND CENTER', 'PROVIDER-NATIVE AURON COMMAND CENTER')
    html = html.replace(
        "E('channel').textContent='VOICE · '+(window.speechSynthesis?'READY':'OFF');",
        "E('channel').textContent=d.brain_provider?'BRAIN · '+d.brain_provider.toUpperCase():'VOICE · '+(window.speechSynthesis?'READY':'OFF');"
    )
    return html
