from app.workspace.models import (
    FileOperation,
    WorkspaceCreate,
    WorkspaceDecision,
    WorkspaceFileChange,
    WorkspacePatch,
    WorkspaceStatus,
)
from app.workspace.service import WorkspaceError, workspace_executor_service


def setup_function() -> None:
    workspace_executor_service.reset()


def _workspace():
    return workspace_executor_service.create(
        WorkspaceCreate(
            repository="ScalpingEdward/JARVIS_os",
            objective="Add a safe workspace executor",
            branch_name="feature/safe-executor",
        )
    )


def _patch() -> WorkspacePatch:
    return WorkspacePatch(
        changes=[
            WorkspaceFileChange(
                path="backend/app/example.py",
                operation=FileOperation.create,
                content="VALUE = 1\n",
            )
        ],
        commit_message="feat: add example",
        pull_request_title="Add example",
    )


def test_patch_requires_human_approval() -> None:
    item = _workspace()
    try:
        workspace_executor_service.attach_patch(item.id, _patch())
    except WorkspaceError as exc:
        assert "Human approval" in str(exc)
    else:
        raise AssertionError("Patch should have been blocked")


def test_workspace_reaches_review_only_after_tests_and_ci() -> None:
    item = _workspace()
    workspace_executor_service.decide(item.id, WorkspaceDecision(approved=True))
    workspace_executor_service.attach_patch(item.id, _patch())
    workspace_executor_service.mark_branch_created(item.id)
    workspace_executor_service.record_tests(item.id, True)
    workspace_executor_service.record_pull_request(item.id, 22, "https://github.com/example/repo/pull/22", "abc123")
    workspace_executor_service.record_ci(item.id, True)
    result = workspace_executor_service.record_review(item.id, WorkspaceDecision(approved=True))

    assert result.success is True
    assert result.workspace.status == WorkspaceStatus.completed
    assert result.workspace.tests_passed is True
    assert result.workspace.ci_passed is True
    assert result.workspace.reviewer_approved is True


def test_protected_paths_are_rejected() -> None:
    item = _workspace()
    workspace_executor_service.decide(item.id, WorkspaceDecision(approved=True))
    patch = WorkspacePatch(
        changes=[
            WorkspaceFileChange(
                path=".env",
                operation=FileOperation.update,
                content="SECRET=x",
            )
        ],
        commit_message="unsafe",
        pull_request_title="unsafe",
    )
    try:
        workspace_executor_service.attach_patch(item.id, patch)
    except WorkspaceError as exc:
        assert "Protected" in str(exc)
    else:
        raise AssertionError("Protected path should have been rejected")
