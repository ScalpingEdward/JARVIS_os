import pytest

from app.core.auron_cross_vertical_integration_certification_v21_580 import (
    CrossVerticalCertificationError,
    CrossVerticalIntegrationCertification,
    VerticalBoundaryEvidence,
)
from app.core.auron_integration_readiness_v21_580 import get_integration_readiness


def evidence(vertical: str, **overrides):
    data = dict(
        vertical=vertical,
        command_centre_present=True,
        persistent_state=True,
        policy_boundary_present=True,
        simulation_present=True,
        execution_boundary_present=True,
        reconciliation_present=True,
        kill_or_disable_control_present=True,
        command_field_present=True,
        recorded_commands_execute_directly=False,
        live_transport_enabled_by_default=False,
    )
    data.update(overrides)
    return VerticalBoundaryEvidence(**data)


def complete_manifest():
    c = CrossVerticalIntegrationCertification()
    return {name: evidence(name) for name in c.REQUIRED_VERTICALS}


def test_all_six_verticals_certify_without_enabling_live_transports():
    decision = CrossVerticalIntegrationCertification().require_certified(complete_manifest())
    assert decision.certified is True
    assert len(decision.verticals) == 6
    assert decision.live_transports_enabled is False
    assert decision.cross_vertical_direct_provider_bypass_allowed is False


def test_missing_vertical_fails_closed():
    manifest = complete_manifest(); manifest.pop('research')
    decision = CrossVerticalIntegrationCertification().certify(manifest)
    assert decision.certified is False
    assert 'missing-vertical-evidence:research' in decision.blockers


def test_live_default_on_is_forbidden():
    manifest = complete_manifest()
    manifest['trading'] = evidence('trading', live_transport_enabled_by_default=True)
    with pytest.raises(CrossVerticalCertificationError):
        CrossVerticalIntegrationCertification().require_certified(manifest)


def test_direct_command_execution_is_forbidden():
    manifest = complete_manifest()
    manifest['automation'] = evidence('automation', recorded_commands_execute_directly=True)
    decision = CrossVerticalIntegrationCertification().certify(manifest)
    assert 'automation:recorded-command-direct-execution-forbidden' in decision.blockers


def test_missing_governance_primitive_fails_closed():
    manifest = complete_manifest()
    manifest['files-documents'] = evidence('files-documents', reconciliation_present=False)
    decision = CrossVerticalIntegrationCertification().certify(manifest)
    assert 'files-documents:reconciliation-missing' in decision.blockers


def test_e1_readiness_advances_to_cross_vertical_simulation_harness():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.580'
    assert readiness['current_item'] == 'E1-cross-vertical-integration-certification'
    assert readiness['next_item'] == 'E2-cross-vertical-end-to-end-simulation-harness'
    assert readiness['live_transports_enabled'] is False
    assert readiness['cross_vertical_direct_provider_bypass_allowed'] is False
