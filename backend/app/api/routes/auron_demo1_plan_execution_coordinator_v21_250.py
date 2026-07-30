from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_goal_aware_planning_v21_249 import (
    _current_step,
    _plan,
    _planning_command,
    command_center as v21_249_command_center,
    dialogue as v21_249_dialogue,
)
from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command, plan_operator_command

router = APIRouter(prefix='/auron/demo1/v21.250', tags=['auron-demo1-plan-execution-coordinator'])


def _route_request(req: DialogueRequest, command: str) -> IntentRouteRequest:
    return IntentRouteRequest(
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        command=command,
        risk_brain_hard_block=req.risk_brain_hard_block,
    )


def _preview(req: DialogueRequest) -> dict:
    plan = _plan(req)
    current = _current_step(plan)
    if current is None:
        return {
            'available': False,
            'plan_step': None,
            'route_state': 'no-step',
            'classification': 'none',
            'approval_required': False,
            'capabilities': [],
            'intents': [],
        }

    route = plan_operator_command(_route_request(req, current['content']))
    capabilities = [
        {
            'adapter_id': step.adapter_id,
            'capability': step.capability,
            'risk': step.risk,
            'approval_required': step.approval_required,
        }
        for step in route.plan
    ]
    if route.state == 'blocked':
        classification = 'blocked'
    elif route.state == 'unsupported':
        classification = 'conversation/manual'
    elif route.approval_required:
        classification = 'approval-required'
    else:
        classification = 'safe-capability'

    return {
        'available': True,
        'plan_step': current['content'],
        'plan_step_index': current['index'],
        'route_state': route.state,
        'classification': classification,
        'approval_required': route.approval_required,
        'capabilities': capabilities,
        'intents': route.detected_intents,
        'reasons': route.reasons,
    }


def _response(mode: str, reply: str, req: DialogueRequest, preview: dict | None = None, **extra) -> dict:
    items = _plan(req)
    current = _current_step(items)
    data = {
        'state': 'completed',
        'mode': mode,
        'reply': reply,
        'detected_intents': ['plan-execution-coordinator'],
        'steps': [],
        'approval_required': bool(preview and preview.get('approval_required')),
        'plan_active': bool(items),
        'plan_steps': items,
        'plan_step_count': len(items),
        'plan_done_count': sum(1 for step in items if step['status'] == 'done'),
        'plan_current_step': current['content'] if current else None,
        'execution_preview': preview,
    }
    data.update(extra)
    return data


def _execution_command(req: DialogueRequest) -> dict | None:
    normalized = ' '.join(req.command.casefold().strip(' .!?').split())
    prepare_terms = {
        'bereite nächsten planschritt vor', 'bereite naechsten planschritt vor',
        'prüfe nächsten planschritt', 'pruefe naechsten planschritt',
        'execution preview', 'zeige execution preview', 'prepare next plan step',
    }
    execute_terms = {
        'führe nächsten planschritt aus', 'fuehre naechsten planschritt aus',
        'nächsten planschritt ausführen', 'naechsten planschritt ausfuehren',
        'execute next plan step', 'execute prepared step',
    }

    if normalized in prepare_terms:
        preview = _preview(req)
        if not preview['available']:
            return _response('plan-execution-preview', 'Es gibt aktuell keinen offenen Planschritt.', req, preview)
        if preview['classification'] == 'safe-capability':
            caps = ', '.join(f"{x['adapter_id']}/{x['capability']}" for x in preview['capabilities'])
            reply = f"Planschritt ist ausführbar und niedriges Risiko. Vorgesehene Capability: {caps}. Noch nichts ausgeführt."
        elif preview['classification'] == 'approval-required':
            reply = 'Planschritt benötigt eine menschliche Freigabe. Noch nichts ausgeführt.'
        elif preview['classification'] == 'blocked':
            reply = 'Planschritt ist durch den Risk-Brain blockiert. Keine Ausführung möglich.'
        else:
            reply = 'Planschritt ist aktuell kein unterstützter Tool-Schritt. Er bleibt als Gesprächs- oder manueller Arbeitsschritt offen.'
        return _response('plan-execution-preview', reply, req, preview)

    if normalized in execute_terms:
        preview = _preview(req)
        if not preview['available']:
            return _response('plan-execution-none', 'Es gibt aktuell keinen offenen Planschritt.', req, preview)
        if preview['classification'] == 'approval-required':
            return _response('plan-execution-approval-required', 'Dieser Planschritt benötigt zuerst deine Freigabe. Ich führe ihn nicht autonom aus.', req, preview)
        if preview['classification'] == 'blocked':
            return _response('plan-execution-blocked', 'Der Risk-Brain blockiert diesen Planschritt. Keine Ausführung.', req, preview)
        if preview['classification'] != 'safe-capability':
            return _response('plan-execution-manual', 'Dieser Planschritt ist aktuell kein sicher ausführbarer Tool-Schritt. Er bleibt offen.', req, preview)

        execution = execute_operator_command(_route_request(req, preview['plan_step']))
        if execution.state != 'completed':
            return _response(
                'plan-execution-failed',
                f'Der Planschritt wurde nicht vollständig abgeschlossen: {execution.state}.',
                req,
                preview,
                execution_state=execution.state,
                execution_steps=[step.model_dump(mode='json') for step in execution.steps],
            )

        completed = _planning_command(DialogueRequest(
            session_id=req.session_id,
            workspace_id=req.workspace_id,
            operator_id=req.operator_id,
            command='Planschritt erledigt',
            risk_brain_hard_block=req.risk_brain_hard_block,
        ))
        reply = 'Planschritt sicher ausgeführt und als erledigt markiert.'
        if completed and completed.get('plan_current_step'):
            reply += f" Als Nächstes: {completed['plan_current_step']}."
        return _response(
            'plan-execution-completed',
            reply,
            req,
            preview,
            execution_state=execution.state,
            execution_steps=[step.model_dump(mode='json') for step in execution.steps],
        )

    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _execution_command(req)
    if direct is not None:
        return direct
    result = v21_249_dialogue(req)
    result['execution_preview'] = _preview(req) if result.get('plan_active') else None
    return result


@router.get('/execution-preview')
def execution_preview(session_id: str, workspace_id: str = 'demo', operator_id: str = 'brano', risk_brain_hard_block: bool = False) -> dict:
    req = DialogueRequest(
        session_id=session_id,
        workspace_id=workspace_id,
        operator_id=operator_id,
        command='execution-preview',
        risk_brain_hard_block=risk_brain_hard_block,
    )
    return _preview(req)


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_249_command_center()
    html = html.replace('v21.249', 'v21.250')
    html = html.replace('GOAL-AWARE PLANNING COMMAND CENTER', 'PLAN EXECUTION COMMAND CENTER')
    html = html.replace(
        "E('approval').textContent=d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO');",
        "E('approval').textContent=d.execution_preview&&d.execution_preview.approval_required?'EXEC · APPROVAL':(d.memory_candidate_pending?'MEMORY · CONFIRM?':'APPROVAL · '+(d.approval_required?'YES':'NO'));"
    )
    return html


from app.api.routes.auron_demo1_execution_queue_v21_251 import router as _auron_v21_251_router
router.routes.extend(_auron_v21_251_router.routes)
