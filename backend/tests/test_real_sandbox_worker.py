from app.sandbox.models import SandboxRunCreate
from app.sandbox.service import sandbox_service
from app.workspace.models import WorkspaceCreate, WorkspaceDecision, WorkspaceFileChange, WorkspacePatch
from app.workspace.service import workspace_executor_service


def setup_function() -> None:
    sandbox_service.reset()
    workspace_executor_service.reset()


def _queued_run():
    workspace = workspace_executor_service.create(
        WorkspaceCreate(repository="owner/repo", objective="Run worker tests", branch_name="feature/worker")
    )
    workspace_executor_service.decide(workspace.id, WorkspaceDecision(approved=True, reason="approved"))
    workspace_executor_service.attach_patch(
        workspace.id,
        WorkspacePatch(
            changes=[WorkspaceFileChange(path="app.py", operation="create", content="print('ok')")],
            commit_message="test: worker",
            pull_request_title="Worker test",
        ),
    )
    return sandbox_service.create(
        SandboxRunCreate(
            workspace_id=workspace.id,
            repository=workspace.repository,
            ref=workspace.branch_name,
            test_command="pytest -q",
        )
    )


def test_claim_next_claims_oldest_queued_run() -> None:
    first = _queued_run()
    second = _queued_run()
    claimed = sandbox_service.claim_next()
    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "running"
    assert sandbox_service.get(second.id).status == "queued"


def test_claim_next_returns_none_when_queue_empty() -> None:
    assert sandbox_service.claim_next() is None


def test_worker_endpoint_returns_204_when_idle(client) -> None:
    response = client.post("/v1/sandbox/worker/claim-next")
    assert response.status_code == 204


def test_worker_source_enforces_network_namespace_and_limits() -> None:
    source = open("../runner/runner.py", encoding="utf-8").read()
    assert "--unshare-all" in source
    assert "RLIMIT_AS" in source
    assert "RLIMIT_CPU" in source
    assert "timeout_seconds" in source
    assert "docker.sock" not in source
    assert "automatic_merge" not in source
