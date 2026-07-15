from app.sandbox.models import SandboxResultIn, SandboxRunCreate
from app.sandbox.service import SandboxError, sandbox_service
from app.workspace.models import WorkspaceCreate, WorkspaceDecision, WorkspaceFileChange, WorkspacePatch
from app.workspace.service import workspace_executor_service


def setup_function() -> None:
    sandbox_service.reset()
    workspace_executor_service.reset()


def _workspace():
    item = workspace_executor_service.create(
        WorkspaceCreate(repository="owner/repo", objective="Run isolated tests", branch_name="feature/test")
    )
    workspace_executor_service.decide(item.id, WorkspaceDecision(approved=True, reason="approved"))
    workspace_executor_service.attach_patch(
        item.id,
        WorkspacePatch(
            changes=[WorkspaceFileChange(path="app.py", operation="create", content="print('ok')")],
            commit_message="feat: test",
            pull_request_title="Test sandbox",
        ),
    )
    return item


def test_sandbox_rejects_network_and_unsafe_commands() -> None:
    item = _workspace()
    try:
        sandbox_service.create(
            SandboxRunCreate(
                workspace_id=item.id,
                repository=item.repository,
                ref=item.branch_name,
                test_command="docker run --privileged x",
                network_enabled=True,
            )
        )
    except SandboxError:
        pass
    else:
        raise AssertionError("unsafe sandbox configuration accepted")


def test_failed_run_creates_fix_prompt_and_blocks_remote_execution() -> None:
    item = _workspace()
    run = sandbox_service.create(
        SandboxRunCreate(
            workspace_id=item.id,
            repository=item.repository,
            ref=item.branch_name,
            test_command="pytest -q",
        )
    )
    sandbox_service.claim(run.id)
    result = sandbox_service.complete(
        run.id,
        SandboxResultIn(exit_code=1, stderr="FAILED test_example.py::test_value - AssertionError"),
    )
    assert result.status == "failed"
    assert "minimal patch" in result.fix_prompt
    assert workspace_executor_service.get(item.id).tests_passed is False


def test_passing_run_opens_remote_gate() -> None:
    item = _workspace()
    run = sandbox_service.create(
        SandboxRunCreate(
            workspace_id=item.id,
            repository=item.repository,
            ref=item.branch_name,
            test_command="pytest -q",
        )
    )
    sandbox_service.claim(run.id)
    result = sandbox_service.complete(run.id, SandboxResultIn(exit_code=0, stdout="12 passed"))
    assert result.status == "passed"
    assert workspace_executor_service.get(item.id).tests_passed is True


def test_status_endpoint_has_no_shell_or_privileged_container(client) -> None:
    response = client.get("/v1/sandbox/status")
    assert response.status_code == 200
    body = response.json()
    assert body["shell_in_api_process"] is False
    assert body["privileged_containers"] is False
    assert body["network_default"] is False
