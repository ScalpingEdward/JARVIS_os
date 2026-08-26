from __future__ import annotations

from app.core.auron_integration_readiness_v21_626 import (
    get_integration_readiness as previous_readiness,
)


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.627",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H19-research-real-provider-transport-injection-contract",
        "completed_gates": tuple(p["completed_gates"])
        + (
            "research-real-transport-interface-shape-defined",
            "research-real-transport-contract-h18-session-bound",
            "research-real-transport-exact-endpoint-capability-enforcement-defined",
            "research-real-transport-request-budget-fail-closed-defined",
            "research-real-transport-timeout-response-size-bounded",
            "research-real-transport-concrete-implementation-absent",
        ),
        "next_item": "H20-research-real-provider-transport-injection-contract-certification",
        "core_next_gate": "research-real-provider-transport-injection-contract-certification",
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
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
