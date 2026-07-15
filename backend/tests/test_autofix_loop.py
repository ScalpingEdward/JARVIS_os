from app.autofix.api import status_info
from app.autofix.models import AutoFixCreate, AutoFixPatch
from app.autofix.service import AutoFixError, autofix_service
from app.sandbox.models import SandboxResultIn, SandboxRunCreate
from app.sandbox.service import sandbox_service
from app.workspace.models import WorkspaceCreate, WorkspaceDecision, WorkspaceFileChange, WorkspacePatch
from app.workspace.service import workspace_executor_service


def setup_function() -> None:
    autofix_service.reset()
    sandbox_service.reset()
    workspace_executor_service.reset()


def _workspace():
    item = workspace_executor_service.create(
        WorkspaceCreate(repository="owner/repo", objective="Repair failing tests", branch_name="feature/autofix")
    )
    workspace_executor_service.decide(item.id, WorkspaceDecision(approved=True, reason="approved"))
    workspace_executor_service.attach_patch(
        item.id,
        WorkspacePatch(
            changes=[WorkspaceFileChange(path="app.py", operation="create", content="value = 1")],
            commit_message="feat: initial patch",
            pull_request_title="Autofix test",
        ),
    )
    return item


def _failed_run(item):
    run = sandbox_service.create(
        SandboxRunCreate(
            workspace_id=item.id,
            repository=item.repository,
            ref=item.branch_name,
            test_command="pytest -q",
        )
    )
    sandbox_service.claim(run.id)
    return sandbox_service.complete(
        run.id,
        SandboxResultIn(exit_code=1, stderr="FAILED test_value - AssertionError"),
    )


def test_failure_creates_bounded_codex_fix_prompt() -> None:
    item = _workspace()
    loop = autofix_service.create(AutoFixCreate(workspace_id=item.id, max_attempts=3))
    result = autofix_service.ingest_sandbox_result(loop.id, _failed_run(item).id)
    assert result.status == "awaiting_patch"
    assert result.attempts == 1
    assert "minimal patch" in result.fix_prompt


def test_patch_queues_new_isolated_sandbox_run() -> None:
    item = _workspace()
    loop = autofix_service.create(AutoFixCreate(workspace_id=item.id, max_attempts=3))
    autofix_service.ingest_sandbox_result(loop.id, _failed_run(item).id)
    result = autofix_service.apply_patch_and_retry(
        loop.id,
        WorkspacePatch(
            changes=[WorkspaceFileChange(path="app.py", operation="update", content="value = 2", expected_sha="abc")],
            commit_message="fix: repair value",
            pull_request_title="Autofix test",
        ),
        AutoFixPatch(attempt=1, summary="Repair failing assertion"),
    )
    assert result.status == "testing"
    assert result.last_sandbox_run_id is not None
    assert sandbox_service.get(result.last_sandbox_run_id).status == "queued"


def test_max_attempts_escalates_to_human() -> None:
    item = _workspace()
    loop = autofix_service.create(AutoFixCreate(workspace_id=item.id, max_attempts=1))
    result = autofix_service.ingest_sandbox_result(loop.id, _failed_run(item).id)
    assert result.status == "escalated"
    assert "Maximum fix attempts" in result.escalation_reason


def test_loop_never_advertises_automatic_merge() -> None:
    body = status_info()
    assert body["automatic_merge"] is False
    assert body["human_escalation"] is True
    assert body["shell_in_api_process"] is False
