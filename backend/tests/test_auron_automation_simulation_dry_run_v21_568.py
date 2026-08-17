from app.automation.auron_automation_policy_approval_v21_567 import AutomationWorkflowPolicy
from app.automation.auron_automation_simulation_dry_run_v21_568 import AutomationSimulationDryRunService
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry
from app.core.auron_integration_readiness_v21_568 import get_integration_readiness


class Catalog:
    def validate_workflow_catalog(self, workflow_id): return ()


def stack(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'workflow.sqlite3')
    workflow = registry.create_workflow(name='W',created_by='operator',now='2026-08-17T10:00:00+00:00')
    registry.add_trigger(workflow.workflow_id,kind='manual',config={},enabled=True,now='2026-08-17T10:00:00+00:00')
    registry.add_action(workflow.workflow_id,ordinal=1,provider_id='p',capability='execute',target_vertical='communications',config={'message':'hello'},now='2026-08-17T10:00:00+00:00')
    registry.add_action(workflow.workflow_id,ordinal=2,provider_id='p',capability='inspect',target_vertical='research',config={'query':'gold'},now='2026-08-17T10:00:00+00:00')
    registry.set_workflow_state(workflow.workflow_id,'ready-for-simulation')
    policy = AutomationWorkflowPolicy(tmp_path/'policy.sqlite3',registry,Catalog())
    policy.approve(workflow.workflow_id,operator_id='op',provider_scope=('p',),vertical_scope=('communications','research'))
    policy.set_kill_switch(workflow.workflow_id,active=False)
    service = AutomationSimulationDryRunService(tmp_path/'simulation.sqlite3',registry,policy)
    return registry, policy, service, workflow.workflow_id


def test_plan_is_deterministic_and_ordered(tmp_path):
    _,_,service,wid = stack(tmp_path)
    first = service.create_plan(wid,operator_id='op')
    second = service.create_plan(wid,operator_id='op')
    assert first.plan_id == second.plan_id
    actions = service.list_actions(first.plan_id)
    assert [a.ordinal for a in actions] == [1,2]
    assert all(a.state == 'simulated-not-executed' for a in actions)


def test_simulation_succeeds_with_zero_execution(tmp_path):
    _,_,service,wid = stack(tmp_path)
    plan = service.create_plan(wid,operator_id='op')
    result = service.simulate(plan.plan_id)
    snapshot = service.inspect(plan.plan_id)
    assert result.state == 'simulated-success'
    assert result.external_calls_made == 0
    assert result.cross_vertical_actions_made == 0
    assert snapshot['provider_writes_made'] == 0
    assert snapshot['cross_vertical_actions_made'] == 0
    assert snapshot['execution_enabled'] is False


def test_policy_drift_blocks_existing_plan(tmp_path):
    _,policy,service,wid = stack(tmp_path)
    plan = service.create_plan(wid,operator_id='op')
    policy.set_kill_switch(wid,active=True)
    assert service.simulate(plan.plan_id).state == 'blocked-policy-drift'


def test_workflow_integrity_drift_blocks_existing_plan(tmp_path):
    registry,_,service,wid = stack(tmp_path)
    plan = service.create_plan(wid,operator_id='op')
    registry.set_workflow_state(wid,'disabled')
    assert service.simulate(plan.plan_id).state in {'blocked-policy-drift','blocked-workflow-drift'}


def test_d21_readiness_advances_to_controlled_execution():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.568'
    assert readiness['next_item'] == 'D22-automation-controlled-execution'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
