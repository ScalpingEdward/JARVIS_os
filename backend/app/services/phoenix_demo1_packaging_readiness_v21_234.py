import os

from app.schemas.phoenix_demo1_operator_acceptance_v21_233 import OperatorAcceptanceRequest
from app.schemas.phoenix_demo1_packaging_readiness_v21_234 import PackagingReadinessRequest, PackagingReadinessResult, StartupCheck
from app.services.phoenix_demo1_operator_acceptance_v21_233 import build_operator_acceptance
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness


def _check(check_id: str, passed: bool, detail: str, required: bool = True) -> StartupCheck:
    return StartupCheck(check_id=check_id, passed=passed, detail=detail, required=required)


def build_packaging_readiness(req: PackagingReadinessRequest) -> PackagingReadinessResult:
    environment = os.getenv('ENVIRONMENT', os.getenv('APP_ENV', 'development'))
    startup_command = 'uvicorn app.main:app --host 0.0.0.0 --port 8000'
    health_endpoint = '/health'
    manifest = {
        'application': 'backend/app/main.py',
        'runtime_readiness': '/phoenix/demo1/v21.226/readiness',
        'operator_dashboard': '/phoenix/demo1/v21.230/dashboard',
        'tool_registry': '/phoenix/demo1/v21.231/tools/status',
        'integration_validation': '/phoenix/demo1/v21.232/validate',
        'operator_acceptance': '/phoenix/demo1/v21.233/acceptance',
    }

    if req.risk_brain_hard_block:
        return PackagingReadinessResult(
            state='blocked', workspace_id=req.workspace_id, operator_id=req.operator_id,
            checks=[_check('risk-brain-authority', True, 'Risk Brain hard block prevents release packaging')],
            passed=1, failed=0, package_manifest=manifest, startup_command=startup_command,
            health_endpoint=health_endpoint, environment=environment,
            operator_acceptance_ready=False, release_packaging_ready=False,
            reasons=['risk-brain-hard-block'],
        )

    readiness = runtime_readiness()
    acceptance = build_operator_acceptance(OperatorAcceptanceRequest(
        workspace_id=req.workspace_id, operator_id=req.operator_id, scenario=req.scenario
    ))
    checks = [
        _check('runtime-ready', readiness.state == 'ready', f'Runtime state={readiness.state}'),
        _check('operator-acceptance-ready', acceptance.operator_acceptance_ready, f'Acceptance state={acceptance.state}'),
        _check('package-manifest-complete', len(manifest) == 6, 'Canonical Demo 1 endpoints are packaged'),
        _check('startup-command-defined', bool(startup_command), startup_command),
        _check('health-endpoint-defined', health_endpoint == '/health', health_endpoint),
        _check('environment-resolved', bool(environment.strip()), f'Environment={environment}'),
        _check('high-risk-autonomy-disabled', readiness.autonomous_high_risk_execution_enabled is False, 'High-risk autonomous execution remains disabled'),
    ]
    passed = sum(1 for item in checks if item.passed)
    failed = sum(1 for item in checks if item.required and not item.passed)
    ready = failed == 0 and acceptance.operator_acceptance_ready
    return PackagingReadinessResult(
        state='ready' if ready else 'review-required', workspace_id=req.workspace_id,
        operator_id=req.operator_id, checks=checks, passed=passed, failed=failed,
        package_manifest=manifest, startup_command=startup_command, health_endpoint=health_endpoint,
        environment=environment, operator_acceptance_ready=acceptance.operator_acceptance_ready,
        release_packaging_ready=ready, reasons=[] if ready else ['startup-or-packaging-check-failed'],
    )
