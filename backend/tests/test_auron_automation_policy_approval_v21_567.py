from app.automation.auron_automation_policy_approval_v21_567 import AutomationWorkflowPolicy, AutomationPolicyError
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry
from app.core.auron_integration_readiness_v21_567 import get_integration_readiness


class Catalog:
    def __init__(self, blockers=()): self.blockers = blockers
    def validate_workflow_catalog(self, workflow_id): return self.blockers


def ready_registry(path):
    r = AutomationWorkflowRegistry(path)
    w = r.create_workflow(name='W',created_by='operator',now='2026-08-17T10:00:00+00:00')
    r.add_trigger(w.workflow_id,kind='manual',config={},enabled=True,now='2026-08-17T10:00:00+00:00')
    r.add_action(w.workflow_id,ordinal=1,provider_id='p',capability='execute',target_vertical='communications',config={},now='2026-08-17T10:00:00+00:00')
    r.set_workflow_state(w.workflow_id,'ready-for-simulation')
    return r,w.workflow_id


def test_approval_is_scoped_and_kill_switch_defaults_on(tmp_path):
    registry,wid = ready_registry(tmp_path/'w.sqlite3')
    policy = AutomationWorkflowPolicy(tmp_path/'p.sqlite3',registry,Catalog())
    approval = policy.approve(wid,operator_id='op',provider_scope=('p',),vertical_scope=('communications',),at='2026-08-17T10:01:00+00:00')
    assert approval.state == 'approved'
    decision = policy.evaluate_authorization(wid,operator_id='op')
    assert decision.allowed is False
    assert 'workflow-kill-switch-active' in decision.blockers


def test_simulation_requires_explicit_kill_switch_release(tmp_path):
    registry,wid = ready_registry(tmp_path/'w.sqlite3')
    policy = AutomationWorkflowPolicy(tmp_path/'p.sqlite3',registry,Catalog())
    policy.approve(wid,operator_id='op',provider_scope=('p',),vertical_scope=('communications',))
    policy.set_kill_switch(wid,active=False)
    decision = policy.require_simulation_authorized(wid,operator_id='op')
    assert decision.allowed is True
    assert decision.external_calls_made == 0


def test_live_execution_remains_fail_closed(tmp_path):
    registry,wid = ready_registry(tmp_path/'w.sqlite3')
    policy = AutomationWorkflowPolicy(tmp_path/'p.sqlite3',registry,Catalog())
    policy.approve(wid,operator_id='op',provider_scope=('p',),vertical_scope=('communications',))
    policy.set_kill_switch(wid,active=False)
    decision = policy.evaluate_authorization(wid,operator_id='op',purpose='execution')
    assert decision.allowed is False
    assert 'D20-live-execution-not-authorized' in decision.blockers


def test_incomplete_scope_is_rejected(tmp_path):
    registry,wid = ready_registry(tmp_path/'w.sqlite3')
    policy = AutomationWorkflowPolicy(tmp_path/'p.sqlite3',registry,Catalog())
    try:
        policy.approve(wid,operator_id='op',provider_scope=('p',),vertical_scope=())
        assert False
    except AutomationPolicyError as exc:
        assert 'vertical scope' in str(exc)


def test_revoked_approval_blocks_authorization(tmp_path):
    registry,wid = ready_registry(tmp_path/'w.sqlite3')
    policy = AutomationWorkflowPolicy(tmp_path/'p.sqlite3',registry,Catalog())
    policy.approve(wid,operator_id='op',provider_scope=('p',),vertical_scope=('communications',))
    policy.set_kill_switch(wid,active=False)
    policy.revoke(wid,operator_id='op')
    decision = policy.evaluate_authorization(wid,operator_id='op')
    assert decision.allowed is False
    assert 'operator-approval-missing' in decision.blockers


def test_catalog_drift_blocks_authorization(tmp_path):
    registry,wid = ready_registry(tmp_path/'w.sqlite3')
    catalog = Catalog()
    policy = AutomationWorkflowPolicy(tmp_path/'p.sqlite3',registry,catalog)
    policy.approve(wid,operator_id='op',provider_scope=('p',),vertical_scope=('communications',))
    policy.set_kill_switch(wid,active=False)
    catalog.blockers = ('action-not-in-provider-catalog:x',)
    assert policy.evaluate_authorization(wid,operator_id='op').allowed is False


def test_d20_readiness_advances_to_simulation():
    r = get_integration_readiness()
    assert r['roadmap_version'] == 'v21.567'
    assert r['next_item'] == 'D21-automation-deterministic-simulation-dry-run'
    assert r['automation_execution_enabled'] is False
