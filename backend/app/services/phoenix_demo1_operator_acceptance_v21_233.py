from app.schemas.phoenix_demo1_integration_validation_v21_232 import DemoScenarioRequest
from app.schemas.phoenix_demo1_operator_acceptance_v21_233 import DemoStep, OperatorAcceptanceRequest, OperatorAcceptanceResult, RecoveryCase
from app.services.phoenix_demo1_integration_validation_v21_232 import run_demo_scenario


def build_operator_acceptance(req: OperatorAcceptanceRequest) -> OperatorAcceptanceResult:
    script = [
        DemoStep(step_id='01-readiness', title='Confirm Demo Runtime', endpoint='/phoenix/demo1/v21.226/readiness', expected_state='ready', recovery_hint='Inspect missing integrations before continuing.'),
        DemoStep(step_id='02-dashboard', title='Open Operator Surface', endpoint='/phoenix/demo1/v21.230/dashboard', expected_state='ready', recovery_hint='Resolve attention panels before continuing.'),
        DemoStep(step_id='03-tools', title='Verify Tool Capabilities', endpoint='/phoenix/demo1/v21.231/tools/status', expected_state='ready', recovery_hint='Keep unavailable capabilities fail-closed.'),
        DemoStep(step_id='04-validation', title='Run End-to-End Validation', endpoint='/phoenix/demo1/v21.232/validate', expected_state='passed', recovery_hint='Review failed scenario checks and rerun.'),
        DemoStep(step_id='05-safety', title='Verify Financial Safety Boundary', endpoint='/phoenix/demo1/v21.231/tools/invoke', expected_state='blocked', recovery_hint='MT5 execution must remain disabled for Demo 1.'),
    ]
    recovery_cases = [
        RecoveryCase(case_id='risk-brain-block', trigger='Risk Brain hard block active', expected_response='Demo acceptance blocked', operator_action='Resolve block; never bypass it.'),
        RecoveryCase(case_id='adapter-unavailable', trigger='Tool capability unavailable or unhealthy', expected_response='Invocation fails closed', operator_action='Restore adapter health or continue with supported fallback.'),
        RecoveryCase(case_id='approval-deferred', trigger='Approval remains deferred', expected_response='No autonomous execution', operator_action='Recover request to pending and approve explicitly when appropriate.'),
        RecoveryCase(case_id='validation-failure', trigger='End-to-end scenario check fails', expected_response='Acceptance remains not ready', operator_action='Inspect failed check, remediate, then rerun validation.'),
    ]

    if req.risk_brain_hard_block:
        return OperatorAcceptanceResult(
            state='blocked', workspace_id=req.workspace_id, operator_id=req.operator_id, scenario=req.scenario,
            script=script, recovery_cases=recovery_cases, integration_acceptance_ready=False,
            operator_acceptance_ready=False, reasons=['risk-brain-hard-block'],
        )

    validation = run_demo_scenario(DemoScenarioRequest(
        scenario=req.scenario, workspace_id=req.workspace_id, operator_id=req.operator_id
    ))
    ready = validation.acceptance_ready and validation.state == 'passed'
    return OperatorAcceptanceResult(
        state='ready' if ready else 'review-required', workspace_id=req.workspace_id,
        operator_id=req.operator_id, scenario=req.scenario, script=script, recovery_cases=recovery_cases,
        integration_acceptance_ready=validation.acceptance_ready, operator_acceptance_ready=ready,
        reasons=[] if ready else ['integration-validation-not-passed'],
    )
