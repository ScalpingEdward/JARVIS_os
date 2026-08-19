import pytest

from app.communications.auron_communications_draft_canary_adapter_v21_601 import (
    CommunicationsDraftCanaryAdapter,CommunicationsDraftCanaryAdapterError)
from app.core.auron_integration_readiness_v21_601 import get_integration_readiness


def adapter(tmp_path): return CommunicationsDraftCanaryAdapter(tmp_path/'communications.db')


def test_render_preview_is_local_idempotent_and_zero_send(tmp_path):
    a=adapter(tmp_path)
    kw=dict(vertical='communications',provider_id='communications-local-draft',scope='draft-preview-only',
        action_key='render-message-preview',payload={'draft_id':'d1','body':'hello'},idempotency_key='k1')
    ref=a.execute_canary_action(**kw); assert a.execute_canary_action(**kw)==ref
    result=a.read_result(provider_ref=ref); preview=a.preview(ref)
    assert result.state=='completed' and result.external_calls_made==0
    assert preview['outbound_send_performed'] is False and preview['provider_write_performed'] is False
    assert preview['network_calls_made']==0


def test_recipient_plan_requires_local_recipient_refs(tmp_path):
    a=adapter(tmp_path)
    ref=a.execute_canary_action(vertical='communications',provider_id='communications-local-draft',scope='recipient-plan-only',
        action_key='inspect-recipient-plan',payload={'draft_id':'d1','recipient_refs':['local://r1','local://r2']},idempotency_key='k2')
    assert a.preview(ref)['recipient_count']==2
    with pytest.raises(CommunicationsDraftCanaryAdapterError):
        a.execute_canary_action(vertical='communications',provider_id='communications-local-draft',scope='recipient-plan-only',
            action_key='inspect-recipient-plan',payload={'draft_id':'d2'},idempotency_key='k3')


def test_outbound_and_provider_transport_fields_fail_closed(tmp_path):
    a=adapter(tmp_path)
    for payload in ({'draft_id':'d','body':'x','send':True},{'draft_id':'d','body':'x','smtp':'x'},
                    {'draft_id':'d','body':'x','provider_write':True}):
        with pytest.raises(CommunicationsDraftCanaryAdapterError):
            a.execute_canary_action(vertical='communications',provider_id='communications-local-draft',scope='draft-preview-only',
                action_key='render-message-preview',payload=payload,idempotency_key=str(payload))


def test_send_action_and_wrong_provider_are_rejected(tmp_path):
    a=adapter(tmp_path)
    with pytest.raises(CommunicationsDraftCanaryAdapterError):
        a.execute_canary_action(vertical='communications',provider_id='communications-local-draft',scope='x',
            action_key='send-message',payload={'draft_id':'d','body':'x'},idempotency_key='x')
    with pytest.raises(CommunicationsDraftCanaryAdapterError):
        a.execute_canary_action(vertical='communications',provider_id='smtp-live',scope='x',
            action_key='render-message-preview',payload={'draft_id':'d','body':'x'},idempotency_key='y')


def test_stop_is_persistent(tmp_path):
    a=adapter(tmp_path); a.stop_canary(activation_id='a1',reason='operator-stop'); assert a.is_stopped('a1') is True


def test_descriptor_and_readiness_keep_outbound_disabled(tmp_path):
    d=adapter(tmp_path).descriptor(); r=get_integration_readiness()
    assert d.side_effect_free is True and d.outbound_send_enabled is False
    assert d.provider_write_enabled is False and d.network_transport_enabled is False and d.production_transport_enabled is False
    assert r['roadmap_version']=='v21.601' and r['next_item']=='G15-communications-canary-end-to-end-certification'
    assert r['communications_outbound_send_enabled'] is False and r['live_transports_enabled'] is False
    assert r['trading_execution_enabled'] is False
