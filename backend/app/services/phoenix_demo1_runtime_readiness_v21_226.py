from app.schemas.phoenix_demo1_runtime_readiness_v21_226 import DemoRuntimeReadiness


def runtime_readiness() -> DemoRuntimeReadiness:
    missing = [
        'concrete-tool-adapters',
    ]
    return DemoRuntimeReadiness(
        version='v21.230',
        state='degraded' if missing else 'ready',
        demo_router_registered=True,
        readiness_router_registered=True,
        voice_adapter_bound=True,
        memory_provider_bound=True,
        approval_store_persistent=True,
        operator_ui_bound=True,
        concrete_tool_adapters_bound=False,
        autonomous_high_risk_execution_enabled=False,
        missing_integrations=missing,
        next_priority='concrete-tool-adapters',
    )
