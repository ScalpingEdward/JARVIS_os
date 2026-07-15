from fastapi.testclient import TestClient

from app.main import app
from app.tools.models import ToolInvocation, ToolRegistration, ToolRisk
from app.tools.service import ToolError, tool_gateway_service

client = TestClient(app)


def setup_function() -> None:
    tool_gateway_service.reset()


def test_default_tool_catalog_is_available() -> None:
    response = client.get("/v1/tools")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 10
    assert {item["kind"] for item in payload["items"]} >= {"github", "telegram", "mt5"}


def test_tool_cannot_be_enabled_before_configuration() -> None:
    tool = tool_gateway_service.list_tools()[0]
    try:
        tool_gateway_service.set_enabled(tool.id, True)
    except ToolError as exc:
        assert "before configuration" in str(exc)
    else:
        raise AssertionError("Unconfigured tool was enabled")


def test_write_invocation_requires_explicit_approval() -> None:
    tool = tool_gateway_service.register(
        ToolRegistration(
            name="Configured GitHub",
            kind="github",
            capabilities=["pull_requests"],
            configured=True,
            enabled=True,
        )
    )
    run = tool_gateway_service.invoke(
        ToolInvocation(
            tool_id=tool.id,
            action="create_pull_request",
            risk=ToolRisk.write,
            approved=False,
        )
    )
    assert run.status == "approval_required"
    assert run.output is None


def test_approved_invocation_uses_adapter_stub_only() -> None:
    tool = tool_gateway_service.register(
        ToolRegistration(
            name="Configured Telegram",
            kind="telegram",
            capabilities=["messages"],
            configured=True,
            enabled=True,
        )
    )
    run = tool_gateway_service.invoke(
        ToolInvocation(
            tool_id=tool.id,
            action="send_message",
            arguments={"chat": "test"},
            risk=ToolRisk.write,
            approved=True,
        )
    )
    assert run.status == "completed"
    assert run.output["mode"] == "adapter_stub"
