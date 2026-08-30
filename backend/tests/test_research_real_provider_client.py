import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.research.real_provider_client import (
    ResearchProviderAuditLog,
    ResearchProviderClient,
    ResearchProviderConfig,
    ResearchProviderFetchError,
)


def _client_with_handler(handler, allowed_domains=("api.github.com",), max_response_bytes=1_000_000, tmp_path=None):
    db_path = str(tmp_path / "audit.db") if tmp_path else ":memory:research:"
    audit = ResearchProviderAuditLog(db_path=db_path if tmp_path else "data/test_research_provider_audit.db")
    transport = httpx.MockTransport(handler)
    return ResearchProviderClient(
        config=ResearchProviderConfig(allowed_domains=allowed_domains, max_response_bytes=max_response_bytes),
        audit_log=audit,
        client=httpx.Client(transport=transport),
    )


def test_rejects_domain_not_on_allowlist(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call must not happen for a disallowed domain")

    client = _client_with_handler(handler, allowed_domains=("api.github.com",), tmp_path=tmp_path)
    with pytest.raises(ResearchProviderFetchError, match="not in the allowlist"):
        client.fetch("https://evil.example.com/data")


def test_rejects_non_https_scheme(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call must not happen for a non-https URL")

    client = _client_with_handler(handler, allowed_domains=("api.github.com",), tmp_path=tmp_path)
    with pytest.raises(ResearchProviderFetchError, match="Only https is allowed"):
        client.fetch("http://api.github.com/data")


def test_enforces_max_response_size(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 100)

    client = _client_with_handler(handler, max_response_bytes=10, tmp_path=tmp_path)
    with pytest.raises(ResearchProviderFetchError, match="exceeded max_response_bytes"):
        client.fetch("https://api.github.com/data")


def test_successful_fetch_returns_content_and_is_audited(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"ok": true}')

    client = _client_with_handler(handler, tmp_path=tmp_path)
    request_id = str(uuid.uuid4())
    result = client.fetch("https://api.github.com/data", request_id=request_id)

    assert result.status_code == 200
    assert result.content == '{"ok": true}'
    assert result.request_id == request_id
    assert client.audit_log.already_succeeded(request_id) is True


def test_exactly_once_rejects_repeated_request_id(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ok")

    client = _client_with_handler(handler, tmp_path=tmp_path)
    request_id = str(uuid.uuid4())
    client.fetch("https://api.github.com/data", request_id=request_id)

    with pytest.raises(ResearchProviderFetchError, match="already executed"):
        client.fetch("https://api.github.com/data", request_id=request_id)


def test_timeout_is_recorded_and_raised(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    client = _client_with_handler(handler, tmp_path=tmp_path)
    with pytest.raises(ResearchProviderFetchError, match="timed out"):
        client.fetch("https://api.github.com/data")


def test_api_endpoint_rejects_disallowed_domain():
    api_client = TestClient(app)
    response = api_client.post("/v1/research/provider/fetch", json={"url": "https://evil.example.com/data"})
    assert response.status_code == 400
    assert "not in the allowlist" in response.json()["detail"]
