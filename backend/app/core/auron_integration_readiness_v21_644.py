from __future__ import annotations

from app.core.auron_integration_readiness_v21_643 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.644",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H36-research-real-provider-network-execution-boundary-design",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-network-execution-h35-authorization-certification-bound",
            "research-real-network-execution-boundary-exactly-once-designed",
            "research-real-network-execution-boundary-expiry-revocation-fail-closed-designed",
            "research-real-network-execution-boundary-readonly-scope-designed",
            "research-real-network-execution-boundary-zero-consumption-zero-network-preserved",
        ),
        "next_item": "H37-research-real-provider-network-execution-boundary-certification",
        "core_next_gate": "research-real-provider-network-execution-boundary-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_network_execution_authorization_designed": True,
        "real_provider_network_execution_authorization_design_certified": True,
        "real_provider_network_execution_authorization_issued": True,
        "real_provider_network_execution_authorization_certified": True,
        "real_provider_network_execution_authorization_consumed": False,
        "real_provider_network_execution_authorization_revocable": True,
        "real_provider_network_execution_boundary_designed": True,
        "real_provider_network_execution_request_reserved": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
