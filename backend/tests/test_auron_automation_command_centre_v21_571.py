import sqlite3
from types import SimpleNamespace

from app.automation.auron_automation_command_centre_v21_571 import (
    AutomationCommandCentre,
    AutomationCommandCentreError,
)
from app.core.auron_integration_readiness_v21_571 import get_integration_readiness


class Registry:
    def __init__(self, db_path): self.db_path = str(db_path)
    def get_workflow(self, workflow_id):
        return SimpleNamespace(workflow_id=workflow_id) if workflow_id == 'wf-1' else None


class Policy:
    def __init__(self, db_path, catalog_path):
        self.db_path = str(db_path)
        self.catalog = SimpleNamespace(db_path=str(catalog_path))
        self.kills = {'wf-1': True}
    def set_kill_switch(self, workflow_id, *, active): self.kills[workflow_id] = active
    def kill_switch_active(self, workflow_id): return self.kills.get(workflow_id, True)


class Execution:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.scope = SimpleNamespace(workflow_id='wf-1',enabled=True,operator_enabled=True,kill_switch=True,updated_at='t')
    def get_scope(self, workflow_id): return self.scope if workflow_id == 'wf-1' else None
    def configure_scope(self, workflow_id, *, enabled, operator_enabled, kill_switch):
        self.scope = SimpleNamespace(workflow_id=workflow_id,enabled=enabled,operator_enabled=operator_enabled,kill_switch=kill_switch,updated_at='t2')
        return self.scope


class Reconciliation:
    def __init__(self, db_path): self.db_path = str(db_path)
    def retry_authorization(self, execution_id):
        if execution_id != 'exec-1': raise RuntimeError('no')
        return SimpleNamespace(execution_id=execution_id,state='retry-eligible')
    def request_cancellation(self, plan_id):
        if plan_id != 'plan-1': raise RuntimeError('no')
        return SimpleNamespace(execution_id='exec-1',cancellation_requested=True,cancellation_state='transport-disabled')


def make_empty_db(path):
    sqlite3.connect(path).close()


def stack(tmp_path):
    paths = {name: tmp_path/f'{name}.sqlite3' for name in ('registry','policy','catalog','simulation','execution','reconciliation','command')}
    for path in paths.values(): make_empty_db(path)
    return AutomationCommandCentre(
        paths['command'], Registry(paths['registry']), Policy(paths['policy'],paths['catalog']),
        SimpleNamespace(db_path=str(paths['simulation'])), Execution(paths['execution']),
        Reconciliation(paths['reconciliation'])
    )


def test_empty_snapshot_preserves_operational_command_field_and_safe_defaults(tmp_path):
    centre = stack(tmp_path)
    snapshot = centre.snapshot()
    assert snapshot['workspace'] == 'automation'
    assert snapshot['command_field_enabled'] is True
    assert snapshot['recorded_commands_execute_directly'] is False
    assert snapshot['automation_execution_enabled_by_default'] is False
    assert snapshot['cross_vertical_execution_enabled_by_default'] is False


def test_command_field_persists_but_never_executes(tmp_path):
    centre = stack(tmp_path)
    entry = centre.record_command('run workflow',actor='operator')
    assert entry.state == 'recorded-not-executed'
    assert centre.get_command(entry.command_id) == entry
    assert centre.list_commands()[0] == entry


def test_policy_kill_switch_is_governed_control(tmp_path):
    centre = stack(tmp_path)
    result = centre.set_policy_kill_switch('wf-1',active=False)
    assert result == {'workflow_id':'wf-1','policy_kill_switch_active':False}


def test_execution_kill_switch_preserves_enablement_state(tmp_path):
    centre = stack(tmp_path)
    result = centre.set_execution_kill_switch('wf-1',active=False)
    assert result['enabled'] is True
    assert result['operator_enabled'] is True
    assert result['kill_switch'] is False


def test_retry_and_cancellation_expose_d23_governed_semantics(tmp_path):
    centre = stack(tmp_path)
    assert centre.retry_status('exec-1')['state'] == 'retry-eligible'
    assert centre.request_cancellation('plan-1')['cancellation_requested'] is True
    try:
        centre.retry_status('unknown')
        assert False
    except AutomationCommandCentreError:
        pass


def test_d24_readiness_completes_automation_architecture_without_default_execution():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.571'
    assert readiness['automation_vertical_architecture_complete'] is True
    assert readiness['next_item'] == 'D25-next-vertical-selection-and-adapter-onboarding'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
