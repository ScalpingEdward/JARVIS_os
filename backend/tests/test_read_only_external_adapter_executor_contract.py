import pytest
from pydantic import ValidationError

from app.schemas.read_only_external_adapter_executor import ReadOnlyExecutionCreate


def base_request(**overrides):
    request = {
        "worker_record_id": "worker-001",
        "gateway_record_id": "gateway-001",
        "dispatch_token_digest": "sha256:dispatch-token",
        "worker_id": "worker-a",
        "adapter_id": "github-readonly-adapter",
        "tool_name": "github",
        "operation": "read-repository",
        "target_host": "api.github.com",
        "target_path": "/repos/ScalpingEdward/JARVIS_os",
        "method": "GET",
        "side_effect_level": "read-only",
    }
    request.update(overrides)
    return request


def create_payload(request):
    return {
        "workspace_id": "ws-a",
        "source_key": "contract-001",
        "requested_by": "planner",
        "request": request,
        "egress_allow_hosts": ["api.github.com"],
        "pinned_hosts": ["api.github.com"],
        "allowed_operations": ["read-repository"],
    }


def test_write_method_rejected_by_schema():
    with pytest.raises(ValidationError):
        ReadOnlyExecutionCreate.model_validate(create_payload(base_request(method="POST")))


def test_unpinned_host_rejected():
    data = create_payload(base_request(target_host="example.com"))
    data["egress_allow_hosts"].append("example.com")
    with pytest.raises(ValidationError, match="target host not pinned"):
        ReadOnlyExecutionCreate.model_validate(data)


def test_host_outside_egress_allow_list_rejected():
    data = create_payload(base_request(target_host="example.com"))
    data["pinned_hosts"].append("example.com")
    with pytest.raises(ValidationError, match="egress allow-list"):
        ReadOnlyExecutionCreate.model_validate(data)


def test_denied_path_prefix_rejected():
    with pytest.raises(ValidationError, match="target path denied"):
        ReadOnlyExecutionCreate.model_validate(create_payload(base_request(target_path="/admin/secrets")))
