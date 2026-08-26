from __future__ import annotations

from app.core.auron_integration_readiness_v21_627 import (
    get_integration_readiness as previous_readiness,
)


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.628",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H20-research-real-provider-transport-injection-contract-certification",
        "completed_gates": tuple(p["completed_gates"])
        + (
            "research-real-transport-contract-h18-session-binding-certified",
            "research-real-transport-interface-semantics-certified",
            "research-real-transport-endpoint-capability-certified",
            "research-real-transport-budget-sequence-certified",
            "research-real-transport-timeout-response-size-certified",
            "research-real-transport-zero-concrete-transport-certified",
        ),
        "next_item": "H21-research-real-provider-transport-injection-activation-design",
        "core_next_gate": "research-real-provider-transport-injection-activation-design",
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
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
