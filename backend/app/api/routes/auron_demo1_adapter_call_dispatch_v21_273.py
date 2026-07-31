from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service

router = APIRouter(prefix='/auron/demo1/v21.273', tags=['auron-demo1-adapter-call-dispatch'])

AdapterCallable = Callable[[dict], dict]
_adapter_registry: dict[str, AdapterCallable] = {}


class AdapterCallDispatchRequest(BaseModel):
    approval_id: UUID
    actor: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    commit_receipt: dict
    adapter_payload: dict = Field(default_factory=dict)
    allow_external_dispatch: bool = False
    emergency_stop_clear: bool = True
    runtime_healthy: bool = True
    adapter_ready: bool = True
    credentials_valid: bool = True
    policy_still_valid: bool = True


def register_dispatch_adapter(name: str, adapter: AdapterCallable) -> None:
    _adapter_registry[name] = adapter


def reset_dispatch_adapters() -> None:
    _adapter_registry.clear()


def _scope_matches(item, payload: AdapterCallDispatchRequest) -> bool:
    return (
        item.arguments.get('session_id') == payload.session_id
        and item.arguments.get('workspace_id') == payload.workspace_id
        and item.requested_by == payload.operator_id
    )


def _validate_commit_receipt(item, payload: AdapterCallDispatchRequest) -> list[str]:
    receipt = payload.commit_receipt
    blockers: list[str] = []
    if receipt.get('approval_id') != str(item.id):
        blockers.append('approval_id')
    if receipt.get('session_id') != payload.session_id:
        blockers.append('session_id')
    if receipt.get('workspace_id') != payload.workspace_id:
        blockers.append('workspace_id')
    if receipt.get('operator_id') != payload.operator_id:
        blockers.append('operator_id')
    if receipt.get('single_use_authorization_consumed') is not True:
        blockers.append('single_use_authorization_consumed')
    if receipt.get('runtime_checks_passed') is not True:
        blockers.append('runtime_checks_passed')
    if receipt.get('invocation_prepared') is not True:
        blockers.append('invocation_prepared')
    if receipt.get('call_committed') is not True:
        blockers.append('call_committed')
    if not receipt.get('adapter'):
        blockers.append('adapter')
    if not receipt.get('execution_domain'):
        blockers.append('execution_domain')
    return blockers


def _dispatch_checks(payload: AdapterCallDispatchRequest) -> dict:
    checks = {
        'emergency_stop_clear': payload.emergency_stop_clear,
        'runtime_healthy': payload.runtime_healthy,
        'adapter_ready': payload.adapter_ready,
        'credentials_valid': payload.credentials_valid,
        'policy_still_valid': payload.policy_still_valid,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {'checks': checks, 'blockers': blockers, 'ready': not blockers}


@router.get('/dispatch-status/{approval_id}')
def dispatch_status(approval_id: UUID) -> dict:
    item = approval_service.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    return {
        'approval_id': str(item.id),
        'approval_status': item.status.value,
        'dispatch_available': item.status == ApprovalStatus.consumed,
        'registered_adapters': sorted(_adapter_registry),
        'adapter_invoked': False,
        'execution_performed': False,
        'external_calls_made': 0,
        'next_gate': 'adapter-call-dispatch',
    }


@router.post('/dispatch')
def dispatch_adapter_call(payload: AdapterCallDispatchRequest) -> dict:
    item = approval_service.get(payload.approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Approval not found')
    if not _scope_matches(item, payload):
        raise HTTPException(status_code=403, detail='Approval scope mismatch')
    if item.status != ApprovalStatus.consumed:
        raise HTTPException(status_code=409, detail='Adapter call dispatch is not authorized')

    receipt_blockers = _validate_commit_receipt(item, payload)
    if receipt_blockers:
        return {
            'state': 'adapter-dispatch-blocked',
            'approval_id': str(item.id),
            'blockers': receipt_blockers,
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'next_gate': 'adapter-call-commit',
        }

    readiness = _dispatch_checks(payload)
    if not readiness['ready']:
        return {
            'state': 'adapter-dispatch-blocked',
            'approval_id': str(item.id),
            **readiness,
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'next_gate': 'preflight-remediation',
        }

    if payload.allow_external_dispatch is not True:
        return {
            'state': 'adapter-dispatch-armed',
            'approval_id': str(item.id),
            **readiness,
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'next_gate': 'adapter-call-dispatch-enable',
            'reply': 'Dispatch ist vorbereitet. Externe Adapter-Ausfuehrung ist noch nicht aktiviert.',
        }

    adapter_name = payload.commit_receipt.get('adapter')
    adapter = _adapter_registry.get(adapter_name)
    if adapter is None:
        return {
            'state': 'adapter-dispatch-blocked',
            'approval_id': str(item.id),
            'blockers': ['adapter_not_registered'],
            'adapter': adapter_name,
            'adapter_invoked': False,
            'execution_performed': False,
            'external_calls_made': 0,
            'next_gate': 'adapter-registration',
        }

    try:
        adapter_result = adapter(
            {
                'approval_id': str(item.id),
                'session_id': payload.session_id,
                'workspace_id': payload.workspace_id,
                'operator_id': payload.operator_id,
                'execution_domain': payload.commit_receipt.get('execution_domain'),
                'payload': payload.adapter_payload,
            }
        )
    except Exception as exc:
        return {
            'state': 'adapter-dispatch-failed',
            'approval_id': str(item.id),
            'adapter': adapter_name,
            'adapter_invoked': True,
            'execution_performed': False,
            'external_calls_made': 1,
            'error_type': type(exc).__name__,
            'next_gate': 'adapter-failure-recovery',
        }

    dispatch_receipt = {
        'approval_id': str(item.id),
        'dispatched_by': payload.actor,
        'session_id': payload.session_id,
        'workspace_id': payload.workspace_id,
        'operator_id': payload.operator_id,
        'adapter': adapter_name,
        'execution_domain': payload.commit_receipt.get('execution_domain'),
        'call_committed': True,
        'adapter_invoked': True,
        'external_calls_made': 1,
    }
    return {
        'state': 'adapter-dispatched',
        'approval_id': str(item.id),
        **readiness,
        'dispatch_receipt': dispatch_receipt,
        'adapter_result': adapter_result,
        'adapter_invoked': True,
        'execution_performed': True,
        'external_calls_made': 1,
        'next_gate': 'adapter-result-verification',
        'reply': 'Adapter wurde kontrolliert aufgerufen. Ergebnis muss jetzt verifiziert werden.',
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_adapter_call_commit_v21_272 import command_center as v21_272_command_center

    html = v21_272_command_center()
    html = html.replace('v21.272', 'v21.273')
    html = html.replace(
        'AURON ADAPTER CALL COMMIT COMMAND CENTER',
        'AURON ADAPTER CALL DISPATCH COMMAND CENTER',
    )
    return html
