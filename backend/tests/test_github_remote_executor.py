import json

import httpx
import pytest

from app.github_remote.service import GitHubRemoteError, GitHubRemoteExecutor
from app.workspace.models import WorkspaceCreate, WorkspaceDecision, WorkspaceFileChange, WorkspacePatch
from app.workspace.service import workspace_executor_service


def setup_function() -> None:
    workspace_executor_service.reset()


def _workspace():
    item = workspace_executor_service.create(
        WorkspaceCreate(
            repository="owner/repo",
            objective="Create a safe remote change",
            branch_name="feature/remote-change",
        )
    )
    workspace_executor_service.decide(item.id, WorkspaceDecision(approved=True, reason="approved"))
    workspace_executor_service.attach_patch(
        item.id,
        WorkspacePatch(
            changes=[WorkspaceFileChange(path="docs/remote.md", operation="create", content="hello")],
            commit_message="docs: add remote file",
            pull_request_title="Add remote file",
            pull_request_body="Automated by JARVIS after approval.",
        ),
    )
    return item


def test_remote_execution_requires_passing_tests() -> None:
    item = _workspace()
    executor = GitHubRemoteExecutor(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))))
    with pytest.raises(GitHubRemoteError, match="Passing sandbox tests"):
        executor.execute(item.id)


def test_remote_execution_creates_branch_commit_and_pr() -> None:
    item = _workspace()
    workspace_executor_service.record_tests(item.id, True, "sandbox green")
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET" and "/git/ref/heads/" in request.url.path:
            return httpx.Response(200, json={"object": {"sha": "base123"}})
        if request.method == "POST" and request.url.path.endswith("/git/refs"):
            return httpx.Response(201, json={"ref": "refs/heads/feature/remote-change"})
        if request.method == "PUT" and "/contents/" in request.url.path:
            payload = json.loads(request.content)
            assert payload["branch"] == "feature/remote-change"
            return httpx.Response(201, json={"commit": {"sha": "commit456"}})
        if request.method == "POST" and request.url.path.endswith("/pulls"):
            return httpx.Response(201, json={"number": 23, "html_url": "https://github.com/owner/repo/pull/23"})
        return httpx.Response(404, text="unexpected")

    client = httpx.Client(base_url="https://api.github.test", transport=httpx.MockTransport(handler))
    result = GitHubRemoteExecutor(client=client).execute(item.id)

    assert result.success is True
    assert result.commit_sha == "commit456"
    assert result.pull_request_number == 23
    assert workspace_executor_service.get(item.id).status == "ci_pending"
    assert ("POST", "/repos/owner/repo/pulls") in calls


def test_sync_ci_records_success_without_merging() -> None:
    item = _workspace()
    workspace_executor_service.record_tests(item.id, True)
    workspace_executor_service.mark_branch_created(item.id)
    workspace_executor_service.record_pull_request(item.id, 23, "https://github.com/owner/repo/pull/23", "commit456")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"state": "success", "statuses": []})

    client = httpx.Client(base_url="https://api.github.test", transport=httpx.MockTransport(handler))
    result = GitHubRemoteExecutor(client=client).sync_ci(item.id)

    assert result.ci_state == "success"
    record = workspace_executor_service.get(item.id)
    assert record.status == "review_pending"
    assert record.reviewer_approved is None


def test_status_endpoint_never_advertises_auto_merge(client) -> None:
    response = client.get("/v1/github-remote/status")
    assert response.status_code == 200
    assert response.json()["automatic_merge"] is False
