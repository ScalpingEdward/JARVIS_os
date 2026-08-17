import pytest

from app.automation.auron_automation_workflow_registry_v21_565 import (
    AutomationWorkflowRegistry,
    AutomationWorkflowRegistryError,
)
from app.core.auron_integration_readiness_v21_565 import get_integration_readiness


def test_workflow_trigger_action_state_is_persistent_and_normalized(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'automation.sqlite3')
    workflow = registry.create_workflow(name='Daily research brief',created_by='operator',now='2026-08-17T12:00:00+00:00')
    trigger = registry.add_trigger(workflow.workflow_id,kind='schedule',provider_id='scheduler',config={'hour': 8},enabled=False,now='2026-08-17T12:01:00+00:00')
    action = registry.add_action(workflow.workflow_id,ordinal=1,provider_id='research',capability='assemble-report',target_vertical='research',config={'confidence':'high'},now='2026-08-17T12:02:00+00:00')
    snapshot = registry.snapshot(workflow.workflow_id)
    assert snapshot['workflow'] == workflow
    assert snapshot['triggers'] == (trigger,)
    assert snapshot['actions'] == (action,)
    assert snapshot['execution_enabled'] is False
    assert snapshot['external_calls_made'] == 0


def test_ids_are_idempotent_for_same_definition(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'automation.sqlite3')
    workflow = registry.create_workflow(name='W',created_by='operator',workflow_id='wf-1',now='2026-08-17T12:00:00+00:00')
    first = registry.add_action(workflow.workflow_id,ordinal=1,provider_id='research',capability='inspect',config={'x':1},now='2026-08-17T12:01:00+00:00')
    second = registry.add_action(workflow.workflow_id,ordinal=1,provider_id='research',capability='inspect',config={'x':1},now='2026-08-17T12:01:00+00:00')
    assert first == second


def test_duplicate_action_ordinal_with_different_action_fails_closed(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'automation.sqlite3')
    workflow = registry.create_workflow(name='W',created_by='operator')
    registry.add_action(workflow.workflow_id,ordinal=1,provider_id='research',capability='inspect',config={})
    with pytest.raises(AutomationWorkflowRegistryError):
        registry.add_action(workflow.workflow_id,ordinal=1,provider_id='communications',capability='draft',config={})


def test_ready_for_simulation_requires_trigger_and_registered_actions(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'automation.sqlite3')
    workflow = registry.create_workflow(name='W',created_by='operator')
    with pytest.raises(AutomationWorkflowRegistryError):
        registry.set_workflow_state(workflow.workflow_id,'ready-for-simulation')
    registry.add_trigger(workflow.workflow_id,kind='manual',config={},enabled=False)
    registry.add_action(workflow.workflow_id,ordinal=1,provider_id='research',capability='inspect',config={})
    ready = registry.set_workflow_state(workflow.workflow_id,'ready-for-simulation')
    assert ready.state == 'ready-for-simulation'


def test_d18_never_exposes_action_execution(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'automation.sqlite3')
    workflow = registry.create_workflow(name='W',created_by='operator')
    snapshot = registry.snapshot(workflow.workflow_id)
    assert snapshot['execution_enabled'] is False
    assert not hasattr(registry, 'execute')
    assert not hasattr(registry, 'run')


def test_d18_readiness_advances_to_d19_without_execution():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.565'
    assert readiness['next_item'] == 'D19-automation-catalog-read-health-integration'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
