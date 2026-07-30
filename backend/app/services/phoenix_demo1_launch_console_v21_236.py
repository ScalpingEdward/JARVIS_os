from app.schemas.phoenix_demo1_launch_console_v21_236 import LaunchConsoleCheck, LaunchConsoleRequest, LaunchConsoleResult
from app.schemas.phoenix_demo1_release_candidate_v21_235 import ReleaseCandidateRequest
from app.services.phoenix_demo1_release_candidate_v21_235 import build_release_candidate


def _check(check_id: str, passed: bool, detail: str) -> LaunchConsoleCheck:
    return LaunchConsoleCheck(check_id=check_id, passed=passed, detail=detail)


def build_launch_console(req: LaunchConsoleRequest) -> LaunchConsoleResult:
    rc = build_release_candidate(ReleaseCandidateRequest(
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        scenario=req.scenario,
        risk_brain_hard_block=req.risk_brain_hard_block,
    ))
    checks = [
        _check('release-candidate-rc1', rc.release_candidate == 'PHOENIX-DEMO1-RC1', f'Release candidate={rc.release_candidate}'),
        _check('final-gate-launch-ready', rc.demo1_launch_ready, f'Final gate state={rc.state}'),
        _check('startup-command-present', bool(rc.startup_command.strip()), rc.startup_command),
        _check('health-endpoint-present', rc.health_endpoint == '/health', rc.health_endpoint),
        _check('operator-dashboard-present', bool(rc.launch_manifest.get('operator_dashboard')), rc.launch_manifest.get('operator_dashboard', 'missing')),
        _check('high-risk-autonomy-disabled', rc.autonomous_high_risk_execution_enabled is False, 'Financial/high-risk autonomous execution remains disabled'),
    ]
    passed = sum(1 for item in checks if item.passed)
    failed = len(checks) - passed
    ready = failed == 0 and rc.demo1_launch_ready
    reasons = list(rc.reasons)
    if not ready and not reasons:
        reasons.append('demo1-launch-preflight-failed')
    return LaunchConsoleResult(
        state='ready-to-start' if ready else ('blocked' if req.risk_brain_hard_block else 'review-required'),
        release_candidate=rc.release_candidate,
        checks=checks,
        passed=passed,
        failed=failed,
        startup_command=rc.startup_command,
        health_endpoint=rc.health_endpoint,
        launch_endpoint='/phoenix/demo1/v21.236/launch-console',
        operator_dashboard=rc.launch_manifest.get('operator_dashboard', '/phoenix/demo1/v21.230/dashboard'),
        demo1_launch_ready=ready,
        next_action='start-local-runtime-and-open-operator-dashboard' if ready else 'resolve-preflight-failures',
        reasons=reasons,
    )
