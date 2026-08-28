from __future__ import annotations

from app.core.auron_integration_readiness_v21_645 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.646",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H38-research-real-provider-network-execution-gate",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-network-execution-h37-boundary-certification-bound",
            "research-real-network-execution-authorization-consumed-exactly-once",
            "research-real-network-execution-one-readonly-request-reserved",
            "research-real-network-execution-expiry-revocation-fail-closed-enforced",
            "research-real-network-execution-provider-traffic-still-disabled",
        ),
        "next_item": "H39-research-real-provider-network-execution-gate-certification",
        "core_next_gate": "research-real-provider-network-execution-gate-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_network_execution_authorization_designed": True,
        "real_provider_network_execution_authorization_design_certified": True,
        "real_provider_network_execution_authorization_issued": True,
        "real_provider_network_execution_authorization_certified": True,
        "real_provider_network_execution_authorization_consumed": True,
        "real_provider_network_execution_authorization_revocable": True,
        "real_provider_network_execution_boundary_designed": True,
        "real_provider_network_execution_boundary_certified": True,
        "real_provider_network_execution_request_reserved": True,
        "real_provider_network_execution_reserved_request_count": 1,
        "real_provider_network_execution_gate_active": True,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
