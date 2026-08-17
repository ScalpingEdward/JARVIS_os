from app.automation.auron_automation_adapter_onboarding_v21_564 import AutomationProviderDescriptor, AutomationProviderHealth
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry
from app.automation.auron_automation_catalog_read_health_v21_566 import AutomationCatalogAction, AutomationCatalogReadHealthIntegration, AutomationCatalogReadHealthError
from app.core.auron_integration_readiness_v21_566 import get_integration_readiness


class Provider:
    def descriptor(self):
        return AutomationProviderDescriptor('p','Provider',('identity','health','catalog','inspect','simulate','execute'),('simulation','read-only'),True,True,False,True,True)
    def read_health(self):
        return AutomationProviderHealth('p',True,True,True,True,True,'2026-08-17T10:00:00+00:00',1)
    def read_catalog(self):
        return (AutomationCatalogAction('p','execute','Execute',{'type':'object'},('communications',),True),)


def test_certified_provider_catalog_is_persisted_without_execution(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'workflow.sqlite3')
    integration = AutomationCatalogReadHealthIntegration(tmp_path/'catalog.sqlite3',registry)
    state = integration.sync(Provider(),observed_at='2026-08-17T10:01:00+00:00')
    assert state.onboarding_accepted is True
    assert state.execution_enabled is False
    assert state.catalog_action_count == 1
    assert integration.get_catalog_action('p','execute').supports_simulation is True


def test_registered_workflow_action_is_validated_against_catalog(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'workflow.sqlite3')
    wf = registry.create_workflow(name='W',created_by='operator',now='2026-08-17T10:00:00+00:00')
    registry.add_action(wf.workflow_id,ordinal=1,provider_id='p',capability='execute',target_vertical='communications',config={},now='2026-08-17T10:00:00+00:00')
    integration = AutomationCatalogReadHealthIntegration(tmp_path/'catalog.sqlite3',registry)
    integration.sync(Provider())
    assert integration.validate_workflow_catalog(wf.workflow_id) == ()


def test_unknown_catalog_action_fails_validation(tmp_path):
    registry = AutomationWorkflowRegistry(tmp_path/'workflow.sqlite3')
    wf = registry.create_workflow(name='W',created_by='operator')
    registry.add_action(wf.workflow_id,ordinal=1,provider_id='p',capability='cancel',config={})
    integration = AutomationCatalogReadHealthIntegration(tmp_path/'catalog.sqlite3',registry)
    integration.sync(Provider())
    assert integration.validate_workflow_catalog(wf.workflow_id)[0].startswith('action-not-in-provider-catalog:')


def test_catalog_provider_identity_mismatch_fails_closed(tmp_path):
    class BadProvider(Provider):
        def read_catalog(self):
            return (AutomationCatalogAction('other','execute','Execute',{},(),True),)
    integration = AutomationCatalogReadHealthIntegration(tmp_path/'catalog.sqlite3',AutomationWorkflowRegistry(tmp_path/'w.sqlite3'))
    try:
        integration.sync(BadProvider())
        assert False
    except AutomationCatalogReadHealthError as exc:
        assert 'identity mismatch' in str(exc)


def test_d19_readiness_advances_to_policy_boundary():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.566'
    assert readiness['next_item'] == 'D20-automation-workflow-policy-approval-boundary'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
