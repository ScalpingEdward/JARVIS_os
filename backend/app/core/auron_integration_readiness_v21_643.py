from __future__ import annotations

from app.core.auron_integration_readiness_v21_642 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.643",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H35-research-real-provider-network-execution-authorization-certification",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-network-execution-h34-authorization-certified",
            "research-real-network-execution-authorization-lineage-certified",
            "research-real-network-execution-authorization-ttl-expiry-certified",
            "research-real-network-execution-authorization-one-shot-scope-certified",
            "research-real-network-execution-authorization-revocation-certified",
            "research-real-network-execution-authorization-zero-consumed-network-certified",
        ),
        "next_item": "H36-research-real-provider-network-execution-boundary-design",
        "core_next_gate": "research-real-provider-network-execution-boundary-design",
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
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
