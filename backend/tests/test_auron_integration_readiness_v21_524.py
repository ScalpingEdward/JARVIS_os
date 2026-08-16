import pytest

from app.core.auron_integration_readiness_v21_524 import assert_external_execution_blocked, get_integration_readiness


def test_checkpoint_and_next_layer_are_explicit() -> None:
    readiness = get_integration_readiness()
    assert readiness['foundation_checkpoint'] == 'v21.523-generation-forty-six-complete'
    assert readiness['current_item'] == 'A1-canonical-roadmap-integration-readiness-registry'
    assert readiness['next_item'] == 'A2-unified-capability-adapter-contract'
    assert readiness['external_calls_made'] == 0


def test_real_verticals_are_blocked_until_core_cutover() -> None:
    readiness = get_integration_readiness()['capabilities']
    for name in ('trading', 'instagram-content-manager'):
        assert readiness[name]['state'] == 'blocked'
        assert readiness[name]['external_execution_enabled'] is False
        assert readiness[name]['next_gate'] == 'core-cutover'
        assert_external_execution_blocked(name)


def test_core_is_foundation_ready_but_not_live() -> None:
    core = get_integration_readiness()['capabilities']['core']
    assert core['state'] == 'foundation-ready'
    assert core['external_execution_enabled'] is False
    assert core['next_gate'] == 'capability-contract'


def test_unknown_capability_fails_closed() -> None:
    with pytest.raises(KeyError):
        assert_external_execution_blocked('unknown-provider')
