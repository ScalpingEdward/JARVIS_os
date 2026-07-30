from app.schemas.phoenix_demo1_runtime_readiness_v21_226 import DemoRuntimeReadiness


def runtime_readiness() -> DemoRuntimeReadiness:
    missing = [
        'persistent-approval-inbox',
        'memory-provider-binding',
        'operator-ui-dashboard',
        'concrete-tool-adapters',
    ]
    return DemoRuntimeReadiness(
        version='v21.227',
        state='degraded' if missing else 'ready',
        demo_router_registered=True,
        readiness_router_registered=True,
        voice_adapter_bound=True,
        memory_provider_bound=False,
        approval_store_persistent=False,
        operator_ui_bound=False,
        concrete_tool_adapters_bound=False,
        autonomous_high_risk_execution_enabled=False,
        missing_integrations=missing,
        next_priority='persistent-approval-inbox',
    )
