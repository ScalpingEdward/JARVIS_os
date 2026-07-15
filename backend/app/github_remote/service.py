import base64
import os
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from app.workspace.models import FileOperation, WorkspaceStatus
from app.workspace.service import WorkspaceError, workspace_executor_service

from .models import GitHubRemoteConfig, RemoteExecutionResponse


class GitHubRemoteError(ValueError):
    pass


class GitHubRemoteExecutor:
    """Executes an already approved workspace through GitHub's REST API.

    This adapter never merges pull requests and never executes shell commands.
    A separate isolated runner must record passing tests before a PR is opened.
    """

    def __init__(self, config: GitHubRemoteConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or GitHubRemoteConfig()
        self._client = client

    def available(self) -> bool:
        return bool(os.getenv(self.config.token_env)) or self._client is not None

    def execute(self, workspace_id: UUID) -> RemoteExecutionResponse:
        item = workspace_executor_service.get(workspace_id)
        if not item.approved:
            raise GitHubRemoteError("Workspace requires human approval")
        if item.patch is None:
            raise GitHubRemoteError("Workspace patch is missing")
        if item.tests_passed is not True:
            raise GitHubRemoteError("Passing sandbox tests are required before remote execution")
        if item.status not in {WorkspaceStatus.ready_for_pr, WorkspaceStatus.running}:
            raise GitHubRemoteError(f"Workspace cannot be remotely executed from status {item.status}")

        client, should_close = self._client_for_request()
        try:
            base_sha = self._get_branch_sha(client, item.repository, item.base_branch)
            self._create_branch(client, item.repository, item.branch_name, base_sha)
            workspace_executor_service.mark_branch_created(item.id)
            commit_sha = base_sha
            for change in item.patch.changes:
                commit_sha = self._apply_change(
                    client,
                    item.repository,
                    item.branch_name,
                    item.patch.commit_message,
                    change.path,
                    change.operation,
                    change.content,
                    change.expected_sha,
                )
            pr = self._open_pull_request(
                client,
                item.repository,
                item.branch_name,
                item.base_branch,
                item.patch.pull_request_title,
                item.patch.pull_request_body,
            )
            workspace_executor_service.record_pull_request(
                item.id,
                number=int(pr["number"]),
                url=str(pr["html_url"]),
                commit_sha=commit_sha,
            )
            item.audit_log.append("Remote GitHub execution completed; merge remains human-only")
            return RemoteExecutionResponse(
                success=True,
                message="Branch, commits, and pull request created",
                workspace_id=str(item.id),
                branch_name=item.branch_name,
                commit_sha=commit_sha,
                pull_request_number=item.pull_request_number,
                pull_request_url=item.pull_request_url,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, WorkspaceError) as exc:
            item.status = WorkspaceStatus.failed
            item.error = str(exc)
            item.audit_log.append(f"Remote GitHub execution failed: {exc}")
            raise GitHubRemoteError(str(exc)) from exc
        finally:
            if should_close:
                client.close()

    def sync_ci(self, workspace_id: UUID) -> RemoteExecutionResponse:
        item = workspace_executor_service.get(workspace_id)
        if item.commit_sha is None or item.pull_request_number is None:
            raise GitHubRemoteError("Workspace pull request does not exist")
        client, should_close = self._client_for_request()
        try:
            response = self._request(client, "GET", f"/repos/{item.repository}/commits/{item.commit_sha}/status")
            state = str(response.get("state", "pending"))
            if state == "success":
                workspace_executor_service.record_ci(item.id, True, "GitHub combined status succeeded")
            elif state in {"failure", "error"}:
                workspace_executor_service.record_ci(item.id, False, f"GitHub combined status: {state}")
            else:
                item.audit_log.append(f"CI still pending: {state}")
            return RemoteExecutionResponse(
                success=state == "success",
                message=f"CI state: {state}",
                workspace_id=str(item.id),
                branch_name=item.branch_name,
                commit_sha=item.commit_sha,
                pull_request_number=item.pull_request_number,
                pull_request_url=item.pull_request_url,
                ci_state=state,
            )
        finally:
            if should_close:
                client.close()

    def _client_for_request(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        token = os.getenv(self.config.token_env)
        if not token:
            raise GitHubRemoteError(f"Missing token environment variable: {self.config.token_env}")
        return httpx.Client(
            base_url=self.config.api_url.rstrip("/"),
            timeout=self.config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        ), True

    def _request(self, client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise GitHubRemoteError(f"GitHub API {response.status_code}: {detail}")
        if response.status_code == 204:
            return {}
        return response.json()

    def _get_branch_sha(self, client: httpx.Client, repository: str, branch: str) -> str:
        data = self._request(client, "GET", f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}")
        return str(data["object"]["sha"])

    def _create_branch(self, client: httpx.Client, repository: str, branch: str, sha: str) -> None:
        self._request(client, "POST", f"/repos/{repository}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha})

    def _apply_change(
        self,
        client: httpx.Client,
        repository: str,
        branch: str,
        message: str,
        path: str,
        operation: FileOperation,
        content: str | None,
        expected_sha: str | None,
    ) -> str:
        endpoint = f"/repos/{repository}/contents/{quote(path, safe='/')}"
        sha = expected_sha
        if operation in {FileOperation.update, FileOperation.delete} and sha is None:
            current = self._request(client, "GET", endpoint, params={"ref": branch})
            sha = str(current["sha"])
        if operation == FileOperation.delete:
            result = self._request(client, "DELETE", endpoint, json={"message": message, "branch": branch, "sha": sha})
        else:
            payload: dict[str, Any] = {
                "message": message,
                "branch": branch,
                "content": base64.b64encode((content or "").encode("utf-8")).decode("ascii"),
            }
            if sha is not None:
                payload["sha"] = sha
            result = self._request(client, "PUT", endpoint, json=payload)
        return str(result["commit"]["sha"])

    def _open_pull_request(
        self,
        client: httpx.Client,
        repository: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        return self._request(
            client,
            "POST",
            f"/repos/{repository}/pulls",
            json={"title": title, "body": body, "head": head, "base": base, "draft": False},
        )


github_remote_executor = GitHubRemoteExecutor()
