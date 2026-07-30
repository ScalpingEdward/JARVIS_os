from app.schemas.phoenix_demo1_integration_validation_v21_232 import DemoScenarioRequest, DemoScenarioResult, ScenarioCheck
from app.schemas.phoenix_demo1_tool_adapters_v21_231 import GovernedToolInvocation
from app.services.phoenix_demo1_operator_dashboard_v21_230 import build_operator_dashboard
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness
from app.services.phoenix_demo1_tool_adapters_v21_231 import adapter_status, invoke_tool
from app.schemas.phoenix_demo1_operator_dashboard_v21_230 import OperatorDashboardRequest


def _check(check_id: str, passed: bool, detail: str) -> ScenarioCheck:
    return ScenarioCheck(check_id=check_id, passed=passed, detail=detail)


def run_demo_scenario(req: DemoScenarioRequest) -> DemoScenarioResult:
    if req.risk_brain_hard_block:
        checks = [_check('risk-brain-authority', True, 'Risk Brain hard block is authoritative')]
        return DemoScenarioResult(
            state='blocked', scenario=req.scenario, workspace_id=req.workspace_id, operator_id=req.operator_id,
            checks=checks, passed=1, failed=0, acceptance_ready=False,
        )

    readiness = runtime_readiness()
    tools = adapter_status()
    dashboard = build_operator_dashboard(OperatorDashboardRequest(workspace_id=req.workspace_id, operator_id=req.operator_id))
    tv = invoke_tool(GovernedToolInvocation(adapter_id='tradingview-sync', capability='status'))
    memory = invoke_tool(GovernedToolInvocation(adapter_id='memory', capability='search', arguments={'query': 'demo'}))
    voice = invoke_tool(GovernedToolInvocation(adapter_id='voice', capability='status'))
    financial = invoke_tool(GovernedToolInvocation(adapter_id='mt5', capability='trade.execute', approved=True))

    checks = [
        _check('runtime-ready', readiness.state == 'ready', f'Runtime state={readiness.state}'),
        _check('dashboard-bound', dashboard.operator_ui_bound is True, 'Operator dashboard is bound'),
        _check('tool-registry-bound', readiness.concrete_tool_adapters_bound is True, f'Healthy capabilities={tools.healthy_count}'),
        _check('tradingview-read-path', tv.state == 'completed', f'TradingView status state={tv.state}'),
        _check('memory-read-path', memory.state == 'completed', f'Memory search state={memory.state}'),
        _check('voice-read-path', voice.state == 'completed', f'Voice status state={voice.state}'),
        _check('financial-execution-disabled', financial.state == 'blocked', f'MT5 execution state={financial.state}'),
        _check('high-risk-autonomy-disabled', readiness.autonomous_high_risk_execution_enabled is False, 'High-risk autonomous execution remains disabled'),
    ]
    passed = sum(1 for item in checks if item.passed)
    failed = len(checks) - passed
    acceptance_ready = failed == 0
    return DemoScenarioResult(
        state='passed' if acceptance_ready else 'failed', scenario=req.scenario,
        workspace_id=req.workspace_id, operator_id=req.operator_id, checks=checks,
        passed=passed, failed=failed, acceptance_ready=acceptance_ready,
    )
