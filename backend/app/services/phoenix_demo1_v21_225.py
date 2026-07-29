import hashlib
import json
from datetime import datetime
from app.schemas.phoenix_demo1_v21_225 import DemoRequest, DemoResponse, DemoApprovalRequest, DemoStatus

_HIGH_RISK = {'high'}


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _interaction_suppressed(req: DemoRequest) -> bool:
    return req.suppress_interaction_until is not None and req.now < req.suppress_interaction_until


def run_demo_vertical_slice(req: DemoRequest) -> DemoResponse:
    approvals: list[DemoApprovalRequest] = []
    executable: list[str] = []
    deferred: list[str] = []

    if req.risk_brain_hard_block:
        state = 'blocked'
        channel = 'silent' if _interaction_suppressed(req) else ('voice' if req.voice_available else 'text')
        summary = 'Risk Brain hard block is active; no governed action may proceed.'
        operator_message = 'PHOENIX is blocked by Risk Brain governance.'
    else:
        healthy_tools = [t for t in req.tools if t.available and t.healthy]
        unhealthy_tools = [t.tool_id for t in req.tools if not (t.available and t.healthy)]
        suppressed = _interaction_suppressed(req) or req.mode in {'focus', 'sleep'}

        needs_approval = req.action_risk in _HIGH_RISK or any(t.requires_approval for t in healthy_tools)
        if needs_approval:
            approval = DemoApprovalRequest(
                approval_id=_digest({'session_id': req.session_id, 'command': req.command, 'risk': req.action_risk})[:20],
                reason='High-risk or explicitly approval-gated action requested.',
                priority=req.priority,
                action_risk=req.action_risk,
            )
            approvals.append(approval)
            if suppressed and req.priority != 'critical':
                deferred.append(req.command)
                state = 'deferred'
            else:
                state = 'queued-for-approval'
        else:
            executable.append(req.command)
            state = 'working'

        if suppressed:
            channel = 'silent'
        elif req.voice_available:
            channel = 'voice'
        elif req.text_available:
            channel = 'text'
        else:
            channel = 'silent'

        parts = []
        if req.memory_context_available:
            parts.append('memory context available')
        if healthy_tools:
            parts.append(f'{len(healthy_tools)} healthy tool(s) available')
        if unhealthy_tools:
            parts.append(f'unhealthy/unavailable tools: {", ".join(sorted(unhealthy_tools))}')
        if approvals:
            parts.append('approval required before gated execution')
        if deferred:
            parts.append('interaction deferred by operator quiet mode')
        summary = '; '.join(parts) if parts else 'Demo request accepted.'

        if state == 'queued-for-approval':
            operator_message = 'Sir? I need your approval before I can continue with this action.'
        elif state == 'deferred':
            operator_message = 'Request recorded and queued. I will surface it when interaction resumes.'
        elif state == 'working':
            operator_message = 'Understood. I can continue with the non-gated work now.'
        else:
            operator_message = 'PHOENIX is ready.'

    payload = {
        'session_id': req.session_id,
        'workspace_id': req.workspace_id,
        'operator_id': req.operator_id,
        'command': req.command,
        'mode': req.mode,
        'priority': req.priority,
        'action_risk': req.action_risk,
        'state': state,
        'channel': channel,
        'approvals': [a.model_dump() for a in approvals],
        'executable': executable,
        'deferred': deferred,
    }
    return DemoResponse(
        state=state,
        interaction_channel=channel,
        summary=summary,
        approval_requests=approvals,
        executable_without_approval=executable,
        deferred_items=deferred,
        operator_message=operator_message,
        audit_digest=_digest(payload),
    )


def demo_status() -> DemoStatus:
    return DemoStatus(
        vertical_slice_ready=True,
        operator_experience_ready=True,
        approval_governance_ready=True,
        memory_path_ready=True,
        voice_or_text_path_ready=True,
        autonomous_high_risk_execution_enabled=False,
        notes=[
            'Demo 1 integrates operator command intake, context availability, quiet modes, approval queueing and safe work continuation.',
            'High-risk execution remains approval-gated.',
            'This slice is intentionally bounded and does not claim every PHOENIX subsystem is production-integrated yet.',
        ],
    )
