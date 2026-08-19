import hashlib
import json
import pytest

from app.content.auron_instagram_draft_preview_canary_adapter_v21_593 import (
    InstagramDraftPreviewCanaryAdapter,
    InstagramDraftPreviewCanaryAdapterError,
)
from app.core.auron_integration_readiness_v21_593 import get_integration_readiness


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def test_descriptor_is_side_effect_free_and_publish_disabled(tmp_path):
    d=InstagramDraftPreviewCanaryAdapter(tmp_path/'i.db').descriptor()
    assert d.vertical=='instagram-content'
    assert d.provider_id=='instagram-local-draft-preview'
    assert d.side_effect_free is True
    assert d.provider_write_enabled is False
    assert d.public_publish_enabled is False
    assert d.network_transport_enabled is False
    assert d.production_transport_enabled is False


def test_render_preview_is_idempotent_and_reconcilable(tmp_path):
    adapter=InstagramDraftPreviewCanaryAdapter(tmp_path/'i.db')
    payload={'draft_id':'draft-1','caption':'hello world','media_refs':['local://image-1']}
    a=adapter.execute_canary_action(vertical='instagram-content',provider_id='instagram-local-draft-preview',
        scope='draft-preview-only',action_key='render-draft-preview',payload=payload,idempotency_key='idem-1')
    b=adapter.execute_canary_action(vertical='instagram-content',provider_id='instagram-local-draft-preview',
        scope='draft-preview-only',action_key='render-draft-preview',payload=payload,idempotency_key='idem-1')
    assert a==b
    r=adapter.read_result(provider_ref=a)
    assert r.state=='completed' and r.payload_hash==payload_hash(payload)
    assert r.external_calls_made==0


def test_metadata_inspection_requires_draft_identity(tmp_path):
    adapter=InstagramDraftPreviewCanaryAdapter(tmp_path/'i.db')
    with pytest.raises(InstagramDraftPreviewCanaryAdapterError):
        adapter.execute_canary_action(vertical='instagram-content',provider_id='instagram-local-draft-preview',
            scope='draft-preview-only',action_key='inspect-draft-metadata',payload={},idempotency_key='idem-2')


def test_publish_write_and_wrong_provider_fail_closed(tmp_path):
    adapter=InstagramDraftPreviewCanaryAdapter(tmp_path/'i.db')
    with pytest.raises(InstagramDraftPreviewCanaryAdapterError):
        adapter.execute_canary_action(vertical='instagram-content',provider_id='instagram-local-draft-preview',
            scope='draft-preview-only',action_key='publish-post',payload={'draft_id':'d'},idempotency_key='idem-3')
    with pytest.raises(InstagramDraftPreviewCanaryAdapterError):
        adapter.execute_canary_action(vertical='instagram-content',provider_id='instagram-api',
            scope='draft-preview-only',action_key='render-draft-preview',payload={'draft_id':'d','caption':'x'},idempotency_key='idem-4')


def test_stop_is_persistent_and_idempotent(tmp_path):
    adapter=InstagramDraftPreviewCanaryAdapter(tmp_path/'i.db')
    adapter.stop_canary(activation_id='a1',reason='operator-stop')
    adapter.stop_canary(activation_id='a1',reason='operator-stop-again')
    assert adapter.is_stopped('a1') is True


def test_g6_readiness_advances_to_g7():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.593'
    assert r['next_item']=='G7-instagram-draft-preview-end-to-end-certification'
    assert r['live_transports_enabled'] is False
