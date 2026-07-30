from app.schemas.phoenix_demo1_packaging_readiness_v21_234 import PackagingReadinessRequest
from app.schemas.phoenix_demo1_release_candidate_v21_235 import FinalGateCheck, ReleaseCandidateRequest, ReleaseCandidateResult
from app.services.phoenix_demo1_packaging_readiness_v21_234 import build_packaging_readiness
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness


_RELEASE_CANDIDATE = 'PHOENIX-DEMO1-RC1'


def _check(check_id: str, passed: bool, detail: str, required: bool = True) -> FinalGateCheck:
    return FinalGateCheck(check_id=check_id, passed=passed, detail=detail, required=required)


def build_release_candidate(req: ReleaseCandidateRequest) -> ReleaseCandidateResult:
    packaging = build_packaging_readiness(PackagingReadinessRequest(
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        scenario=req.scenario,
        risk_brain_hard_block=req.risk_brain_hard_block,
    ))
    readiness = runtime_readiness()
    launch_manifest = dict(packaging.package_manifest)
    launch_manifest.update({
        'packaging_readiness': '/phoenix/demo1/v21.234/packaging-readiness',
        'release_candidate_gate': '/phoenix/demo1/v21.235/release-candidate',
        'health': packaging.health_endpoint,
    })

    if req.risk_brain_hard_block:
        return ReleaseCandidateResult(
            state='blocked', workspace_id=req.workspace_id, operator_id=req.operator_id,
            checks=[_check('risk-brain-authority', True, 'Risk Brain hard block prevents Demo 1 launch')],
            passed=1, failed=0, release_candidate=_RELEASE_CANDIDATE,
            launch_manifest=launch_manifest, startup_command=packaging.startup_command,
            health_endpoint=packaging.health_endpoint, environment=packaging.environment,
            operator_acceptance_ready=False, release_packaging_ready=False,
            demo1_launch_ready=False, reasons=['risk-brain-hard-block'],
        )

    checks = [
        _check('runtime-ready', readiness.state == 'ready', f'Runtime state={readiness.state}'),
        _check('operator-acceptance-ready', packaging.operator_acceptance_ready, 'Operator acceptance gate passed'),
        _check('release-packaging-ready', packaging.release_packaging_ready, f'Packaging state={packaging.state}'),
        _check('startup-contract-present', bool(packaging.startup_command), packaging.startup_command),
        _check('health-contract-present', packaging.health_endpoint == '/health', packaging.health_endpoint),
        _check('launch-manifest-complete', len(launch_manifest) >= 9, f'Launch manifest entries={len(launch_manifest)}'),
        _check('high-risk-autonomy-disabled', readiness.autonomous_high_risk_execution_enabled is False, 'High-risk autonomous execution remains disabled'),
    ]
    passed = sum(1 for item in checks if item.passed)
    failed = sum(1 for item in checks if item.required and not item.passed)
    launch_ready = failed == 0 and packaging.release_packaging_ready and packaging.operator_acceptance_ready

    return ReleaseCandidateResult(
        state='launch-ready' if launch_ready else 'review-required',
        workspace_id=req.workspace_id, operator_id=req.operator_id,
        checks=checks, passed=passed, failed=failed, release_candidate=_RELEASE_CANDIDATE,
        launch_manifest=launch_manifest, startup_command=packaging.startup_command,
        health_endpoint=packaging.health_endpoint, environment=packaging.environment,
        operator_acceptance_ready=packaging.operator_acceptance_ready,
        release_packaging_ready=packaging.release_packaging_ready,
        demo1_launch_ready=launch_ready,
        reasons=[] if launch_ready else ['final-demo1-gate-not-satisfied'],
    )
