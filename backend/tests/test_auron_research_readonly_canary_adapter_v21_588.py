import hashlib
import json
import pytest

from app.research.auron_research_readonly_canary_adapter_v21_588 import (
    ResearchReadonlyCanaryAdapter,
    ResearchReadonlyCanaryAdapterError,
)
from app.core.auron_integration_readiness_v21_588 import get_integration_readiness


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def test_descriptor_is_read_only_and_production_disabled(tmp_path):
    adapter = ResearchReadonlyCanaryAdapter(tmp_path/'r.db')
    d = adapter.descriptor()
    assert d.vertical == 'research'
    assert d.provider_id == 'research-local-readonly'
    assert d.read_only is True
    assert d.network_transport_enabled is False
    assert d.production_transport_enabled is False


def test_search_preview_is_idempotent_and_reconcilable(tmp_path):
    adapter = ResearchReadonlyCanaryAdapter(tmp_path/'r.db')
    payload = {'query': 'gold macro outlook'}
    a = adapter.execute_canary_action(
        vertical='research', provider_id='research-local-readonly', scope='preview-only',
        action_key='search-preview', payload=payload, idempotency_key='idem-1')
    b = adapter.execute_canary_action(
        vertical='research', provider_id='research-local-readonly', scope='preview-only',
        action_key='search-preview', payload=payload, idempotency_key='idem-1')
    assert a == b
    result = adapter.read_result(provider_ref=a)
    assert result.state == 'completed'
    assert result.payload_hash == payload_hash(payload)
    assert result.external_calls_made == 0


def test_metadata_inspection_requires_source_identity(tmp_path):
    adapter = ResearchReadonlyCanaryAdapter(tmp_path/'r.db')
    with pytest.raises(ResearchReadonlyCanaryAdapterError):
        adapter.execute_canary_action(
            vertical='research', provider_id='research-local-readonly', scope='preview-only',
            action_key='inspect-source-metadata', payload={}, idempotency_key='idem-2')


def test_wrong_vertical_provider_or_action_fails_closed(tmp_path):
    adapter = ResearchReadonlyCanaryAdapter(tmp_path/'r.db')
    with pytest.raises(ResearchReadonlyCanaryAdapterError):
        adapter.execute_canary_action(
            vertical='trading', provider_id='research-local-readonly', scope='preview-only',
            action_key='search-preview', payload={'query':'x'}, idempotency_key='idem-3')
    with pytest.raises(ResearchReadonlyCanaryAdapterError):
        adapter.execute_canary_action(
            vertical='research', provider_id='other', scope='preview-only',
            action_key='search-preview', payload={'query':'x'}, idempotency_key='idem-4')
    with pytest.raises(ResearchReadonlyCanaryAdapterError):
        adapter.execute_canary_action(
            vertical='research', provider_id='research-local-readonly', scope='preview-only',
            action_key='write-anything', payload={'query':'x'}, idempotency_key='idem-5')


def test_stop_boundary_is_persistent_and_idempotent(tmp_path):
    adapter = ResearchReadonlyCanaryAdapter(tmp_path/'r.db')
    adapter.stop_canary(activation_id='a1', reason='policy drift')
    assert adapter.is_stopped('a1') is True
    adapter.stop_canary(activation_id='a1', reason='updated reason')
    assert adapter.is_stopped('a1') is True


def test_g1_readiness_advances_to_provider_specific_e2e_harness():
    r = get_integration_readiness()
    assert r['roadmap_version'] == 'v21.588'
    assert r['current_item'] == 'G1-research-readonly-canary-adapter-integration'
    assert r['next_item'] == 'G2-research-canary-end-to-end-certification-harness'
    assert r['live_transports_enabled'] is False
