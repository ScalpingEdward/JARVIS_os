from app.automation.auron_automation_controlled_execution_v21_569 import ControlledAutomationExecutionService
from app.automation.auron_automation_policy_approval_v21_567 import AutomationWorkflowPolicy
from app.automation.auron_automation_simulation_dry_run_v21_568 import AutomationSimulationDryRunService
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry
from app.core.auron_integration_readiness_v21_569 import get_integration_readiness


class Catalog:
    def validate_workflow_catalog(self, workflow_id): return ()


def stack(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'workflow.sqlite3')
    workflow = registry.create_workflow(name='W',created_by='operator',now='2026-08-17T10:00:00+00:00')
    registry.add_trigger(workflow.workflow_id,kind='manual',config={},enabled=True,now='2026-08-17T10:00:00+00:00')
    registry.add_action(workflow.workflow_id,ordinal=1,provider_id='p',capability='execute',target_vertical='communications',config={'message':'hello'},now='2026-08-17T10:00:00+00:00')
    registry.set_workflow_state(workflow.workflow_id,'ready-for-simulation')
    policy = AutomationWorkflowPolicy(tmp_path/'policy.sqlite3',registry,Catalog())
    policy.approve(workflow.workflow_id,operator_id='op',provider_scope=('p',),vertical_scope=('communications',))
    policy.set_kill_switch(workflow.workflow_id,active=False)
    simulation = AutomationSimulationDryRunService(tmp_path/'simulation.sqlite3',registry,policy)
    plan = simulation.create_plan(workflow.workflow_id,operator_id='op')
    assert simulation.simulate(plan.plan_id).state == 'simulated-success'
    execution = ControlledAutomationExecutionService(tmp_path/'execution.sqlite3',registry,policy,simulation)
    return registry,policy,simulation,execution,plan


def test_missing_execution_scope_fails_closed(tmp_path):
    _,_,_,execution,plan = stack(tmp_path)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'execution-scope-missing' in decision.blockers
    assert decision.external_calls_made == 0


def test_scope_requires_operator_and_clear_kill_switch(tmp_path):
    _,_,_,execution,plan = stack(tmp_path)
    execution.configure_scope(plan.workflow_id,enabled=True,operator_enabled=False,kill_switch=True)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'operator-enablement-required' in decision.blockers
    assert 'execution-kill-switch-active' in decision.blockers


def test_ready_scope_reaches_boundary_but_default_transport_is_disabled(tmp_path):
    _,_,_,execution,plan = stack(tmp_path)
    execution.configure_scope(plan.workflow_id,enabled=True,operator_enabled=True,kill_switch=False)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'ready-for-controlled-execution'
    result = execution.execute(plan.plan_id)
    assert result.state == 'execution-transport-disabled'
    assert result.external_calls_made == 0
    assert result.cross_vertical_actions_made == 0


def test_policy_drift_after_simulation_blocks_execution(tmp_path):
    _,policy,_,execution,plan = stack(tmp_path)
    execution.configure_scope(plan.workflow_id,enabled=True,operator_enabled=True,kill_switch=False)
    policy.set_kill_switch(plan.workflow_id,active=True)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'current-d20-authorization-required' in decision.blockers


def test_execution_decision_is_idempotent(tmp_path):
    _,_,_,execution,plan = stack(tmp_path)
    first = execution.evaluate(plan.plan_id)
    second = execution.evaluate(plan.plan_id)
    assert first.execution_id == second.execution_id
    assert first == second


def test_d22_readiness_advances_to_reconciliation():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.569'
    assert readiness['next_item'] == 'D23-automation-reconciliation-retries-cancellation'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
    assert readiness['automation_execution_transport_available'] is False
