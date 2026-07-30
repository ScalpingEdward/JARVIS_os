import hashlib
import json

from app.schemas.phoenix_demo1_execution_orchestrator_v21_237 import (
    ExecutionOrchestratorRequest,
    ExecutionOrchestratorResult,
    ExecutionStepResult,
)
from app.schemas.phoenix_demo1_operator_dashboard_v21_230 import OperatorDashboardRequest
from app.schemas.phoenix_demo1_tool_adapters_v21_231 import GovernedToolInvocation
from app.services.phoenix_demo1_operator_dashboard_v21_230 import build_operator_dashboard
from app.services.phoenix_demo1_tool_adapters_v21_231 import adapter_status, invoke_tool


def _digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _step(step_id: str, adapter_id: str, capability: str, state: str, summary: str, output: dict | None = None, reasons: list[str] | None = None) -> ExecutionStepResult:
    return ExecutionStepResult(
        step_id=step_id,
        adapter_id=adapter_id,
        capability=capability,
        state=state,
        summary=summary,
        output=output,
        reasons=reasons or [],
    )


def _invoke(step_id: str, adapter_id: str, capability: str, arguments: dict | None = None) -> ExecutionStepResult:
    result = invoke_tool(GovernedToolInvocation(
        adapter_id=adapter_id,
        capability=capability,
        arguments=arguments or {},
        approved=False,
        risk_brain_hard_block=False,
    ))
    return _step(
        step_id,
        adapter_id,
        capability,
        result.state,
        f'{adapter_id}/{capability}: {result.state}',
        output=result.output,
        reasons=result.reasons,
    )


def execute_demo_command(req: ExecutionOrchestratorRequest) -> ExecutionOrchestratorResult:
    if req.risk_brain_hard_block:
        payload = {
            'version': 'v21.237',
            'state': 'blocked',
            'session_id': req.session_id,
            'workspace_id': req.workspace_id,
            'operator_id': req.operator_id,
            'requested_command': req.command,
            'steps': [],
            'completed_steps': 0,
            'failed_steps': 0,
            'operator_summary': 'Execution blocked by Risk Brain hard block.',
            'approval_required': False,
            'autonomous_high_risk_execution_enabled': False,
            'reasons': ['risk-brain-hard-block'],
        }
        payload['audit_digest'] = _digest(payload)
        return ExecutionOrchestratorResult(**payload)

    steps: list[ExecutionStepResult] = []

    dashboard = build_operator_dashboard(OperatorDashboardRequest(
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        risk_brain_hard_block=False,
    ))
    steps.append(_step(
        'system-readiness',
        'phoenix-demo1',
        'operator-dashboard.snapshot',
        'completed' if dashboard.state == 'ready' else 'degraded',
        f'Operator dashboard state={dashboard.state}; attention={len(dashboard.attention_panels)}',
        output=dashboard.model_dump(mode='json'),
    ))

    steps.append(_invoke('voice-status', 'voice', 'status'))
    steps.append(_invoke('approval-inbox', 'approvals', 'list'))

    memory_query = (req.memory_query or req.command).strip()
    steps.append(_invoke('memory-search', 'memory', 'search', {'query': memory_query}))
    steps.append(_invoke('tradingview-status', 'tradingview-sync', 'status'))

    registry = adapter_status()
    steps.append(_step(
        'tool-registry',
        'phoenix-demo1',
        'tools.registry',
        'completed',
        f'{registry.healthy_count} healthy capabilities; {registry.unavailable_count} unavailable or gated',
        output=registry.model_dump(mode='json'),
    ))

    completed = sum(1 for item in steps if item.state == 'completed')
    failed = sum(1 for item in steps if item.state not in {'completed'})
    state = 'completed' if failed == 0 else ('partial' if completed > 0 else 'failed')

    dashboard_state = dashboard.state
    approval_items = next((s.output.get('items', []) for s in steps if s.step_id == 'approval-inbox' and s.output), [])
    memory_items = next((s.output.get('items', []) for s in steps if s.step_id == 'memory-search' and s.output), [])
    unavailable = registry.unavailable_count
    operator_summary = (
        f'PHOENIX execution complete: system={dashboard_state}; '
        f'approvals={len(approval_items)}; memory_matches={len(memory_items)}; '
        f'tools_healthy={registry.healthy_count}; tools_unavailable={unavailable}; '
        f'voice_bound={dashboard.voice_adapter_bound}; result={state}.'
    )

    payload = {
        'version': 'v21.237',
        'state': state,
        'session_id': req.session_id,
        'workspace_id': req.workspace_id,
        'operator_id': req.operator_id,
        'requested_command': req.command,
        'steps': [item.model_dump(mode='json') for item in steps],
        'completed_steps': completed,
        'failed_steps': failed,
        'operator_summary': operator_summary,
        'approval_required': False,
        'autonomous_high_risk_execution_enabled': False,
        'reasons': [] if state == 'completed' else ['one-or-more-read-only-steps-not-completed'],
    }
    payload['audit_digest'] = _digest(payload)
    return ExecutionOrchestratorResult(**payload)
