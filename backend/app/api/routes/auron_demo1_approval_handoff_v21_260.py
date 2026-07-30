from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.approvals.models import ActorRole, ApprovalRequestCreate, ApprovalStatus, RiskLevel
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.260', tags=['auron-demo1-approval-handoff'])


def _pending_for(req: DialogueRequest) -> list:
    items = approval_service.list(status=ApprovalStatus.pending)
    return [
        item
        for item in items
        if item.requested_by == req.operator_id
        and item.arguments.get('session_id') == req.session_id
    ]


def _existing(req: DialogueRequest):
    command = req.command.strip()
    for item in _pending_for(req):
        if item.arguments.get('command') == command:
            return item
    return None


def _request_approval(req: DialogueRequest, policy: dict):
    existing = _existing(req)
    if existing is not None:
        return existing

    return approval_service.request(
        ApprovalRequestCreate(
            action='auron.execute.high_risk',
            arguments={
                'command': req.command.strip()[:500],
                'session_id': req.session_id,
                'workspace_id': req.workspace_id,
                'operator_id': req.operator_id,
                'policy_mode': policy.get('mode'),
                'policy_reason': policy.get('reason'),
            },
            requested_by=req.operator_id,
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason=f"AURON policy requires approval: {policy.get('reason', 'high-risk execution')}",
        )
    )


def _serialize(item) -> dict:
    return {
        'approval_id': str(item.id),
        'status': item.status.value,
        'action': item.action,
        'command': item.arguments.get('command'),
        'risk': item.risk.value,
        'reason': item.reason,
        'requested_by': item.requested_by,
        'created_at': item.created_at.isoformat(),
    }


def _command(req: DialogueRequest) -> dict | None:
    text = ' '.join(req.command.casefold().strip(' .!?').split())
    if text in {'approval status', 'freigabe status', 'offene freigaben', 'pending approvals'}:
        items = [_serialize(item) for item in _pending_for(req)]
        return {
            'state': 'completed',
            'mode': 'approval-handoff-status',
            'reply': f'Offene Freigaben: {len(items)}.',
            'detected_intents': ['approval-handoff'],
            'steps': [],
            'approval_required': False,
            'approvals': items,
        }
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _command(req)
    if direct is not None:
        return direct

    # Import downstream AURON layers only when this endpoint is actually used.
    # This keeps application startup independent from the historical router-chain
    # import order and prevents v21.260 from exposing latent circular imports.
    from app.api.routes.auron_demo1_execution_policy_controller_v21_258 import _policy
    from app.api.routes.auron_demo1_policy_decision_ledger_v21_259 import dialogue as v21_259_dialogue

    policy = _policy(req)
    if policy.get('mode') == 'approval-required':
        approval = _request_approval(req, policy)
        return {
            'state': 'approval-required',
            'mode': 'approval-handoff-created',
            'reply': f'Freigabe angefordert. Approval ID: {approval.id}. Es wurde nichts ausgeführt.',
            'detected_intents': ['approval-handoff'],
            'steps': [],
            'approval_required': True,
            'approval': _serialize(approval),
            'policy': policy,
            'execution_performed': False,
        }

    result = v21_259_dialogue(req)
    result['approval_handoff'] = {'required': False, 'created': False}
    return result


@router.get('/pending')
def pending(
    session_id: str = 'approval',
    workspace_id: str = 'demo',
    operator_id: str = 'brano',
) -> dict:
    req = DialogueRequest(
        session_id=session_id,
        workspace_id=workspace_id,
        operator_id=operator_id,
        command='approval status',
    )
    items = [_serialize(item) for item in _pending_for(req)]
    return {'count': len(items), 'items': items}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_policy_decision_ledger_v21_259 import command_center as v21_259_command_center

    html = v21_259_command_center()
    html = html.replace('v21.259', 'v21.260')
    html = html.replace(
        'AURON POLICY DECISION LEDGER COMMAND CENTER',
        'AURON APPROVAL HANDOFF COMMAND CENTER',
    )
    return html
