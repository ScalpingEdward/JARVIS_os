from __future__ import annotations

from app.core.auron_integration_readiness_v21_628 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.629",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H21-research-real-provider-transport-injection-activation-design",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-activation-h20-certification-bound",
            "research-real-transport-activation-read-only-design-defined",
            "research-real-transport-activation-opaque-transport-ref-defined",
            "research-real-transport-activation-operator-reapproval-kill-rollback-required",
            "research-real-transport-activation-not-authorized-not-injected",
        ),
        "next_item": "H22-research-real-provider-transport-injection-activation-design-certification",
        "core_next_gate": "research-real-provider-transport-injection-activation-design-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_canary_token_enabled": True,
        "real_provider_canary_execution_boundary_designed": True,
        "real_provider_canary_execution_boundary_certified": True,
        "real_provider_canary_session_gate_enabled": True,
        "real_provider_transport_injection_contract_defined": True,
        "real_provider_transport_injection_contract_certified": True,
        "real_provider_transport_injection_activation_designed": True,
        "real_provider_transport_injection_authorized": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
