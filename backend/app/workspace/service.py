from datetime import datetime, timezone
from uuid import UUID

from .models import (
    FileOperation,
    WorkspaceCreate,
    WorkspaceDecision,
    WorkspacePatch,
    WorkspaceRecord,
    WorkspaceResult,
    WorkspaceStatus,
)


class WorkspaceError(ValueError):
    pass


class WorkspaceExecutorService:
    """Stateful safety gateway for GitHub/Codex workspace execution.

    Provider-specific GitHub and sandbox adapters call these transitions after
    completing their external operation. The service prevents PR/merge flow
    from bypassing approval, tests, CI, or reviewer gates.
    """

    PROTECTED_PATHS = {".git", ".env", "secrets", "credentials"}

    def __init__(self) -> None:
        self._items: dict[UUID, WorkspaceRecord] = {}

    def reset(self) -> None:
        self._items.clear()

    def create(self, payload: WorkspaceCreate) -> WorkspaceRecord:
        item = WorkspaceRecord(**payload.model_dump())
        item.audit_log.append("Workspace plan created")
        self._items[item.id] = item
        return item

    def list_all(self) -> list[WorkspaceRecord]:
        return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, workspace_id: UUID) -> WorkspaceRecord:
        item = self._items.get(workspace_id)
        if item is None:
            raise WorkspaceError("Workspace not found")
        return item

    def decide(self, workspace_id: UUID, decision: WorkspaceDecision) -> WorkspaceRecord:
        item = self.get(workspace_id)
        if item.status != WorkspaceStatus.planned:
            raise WorkspaceError("Workspace approval is no longer pending")
        item.approved = decision.approved
        item.status = WorkspaceStatus.approved if decision.approved else WorkspaceStatus.blocked
        item.audit_log.append(f"Human approval: {decision.approved}. {decision.reason}".strip())
        self._touch(item)
        return item

    def attach_patch(self, workspace_id: UUID, patch: WorkspacePatch) -> WorkspaceRecord:
        item = self.get(workspace_id)
        if item.require_human_approval and not item.approved:
            raise WorkspaceError("Human approval is required before attaching executable changes")
        self._validate_patch(patch)
        item.patch = patch
        item.status = WorkspaceStatus.running
        item.audit_log.append(f"Patch attached with {len(patch.changes)} file changes")
        self._touch(item)
        return item

    def mark_branch_created(self, workspace_id: UUID) -> WorkspaceRecord:
        item = self.get(workspace_id)
        self._require_patch(item)
        item.branch_created = True
        item.audit_log.append(f"Branch created: {item.branch_name}")
        self._touch(item)
        return item

    def record_tests(self, workspace_id: UUID, passed: bool, details: str = "") -> WorkspaceRecord:
        item = self.get(workspace_id)
        self._require_patch(item)
        item.tests_passed = passed
        item.status = WorkspaceStatus.ready_for_pr if passed else WorkspaceStatus.failed
        item.error = None if passed else (details or "Tests failed")
        item.audit_log.append(f"Tests passed: {passed}. {details}".strip())
        self._touch(item)
        return item

    def record_pull_request(self, workspace_id: UUID, number: int, url: str, commit_sha: str) -> WorkspaceRecord:
        item = self.get(workspace_id)
        if not item.branch_created:
            raise WorkspaceError("Branch must exist before opening a pull request")
        if item.tests_passed is not True:
            raise WorkspaceError("Tests must pass before opening a pull request")
        item.pull_request_number = number
        item.pull_request_url = url
        item.commit_sha = commit_sha
        item.status = WorkspaceStatus.ci_pending if item.require_green_ci else WorkspaceStatus.review_pending
        item.audit_log.append(f"Pull request opened: #{number}")
        self._touch(item)
        return item

    def record_ci(self, workspace_id: UUID, passed: bool, details: str = "") -> WorkspaceRecord:
        item = self.get(workspace_id)
        if item.pull_request_number is None:
            raise WorkspaceError("Pull request must exist before CI can be recorded")
        item.ci_passed = passed
        item.status = WorkspaceStatus.review_pending if passed else WorkspaceStatus.failed
        item.error = None if passed else (details or "CI failed")
        item.audit_log.append(f"CI passed: {passed}. {details}".strip())
        self._touch(item)
        return item

    def record_review(self, workspace_id: UUID, decision: WorkspaceDecision) -> WorkspaceResult:
        item = self.get(workspace_id)
        if item.require_green_ci and item.ci_passed is not True:
            raise WorkspaceError("Green CI is required before reviewer approval")
        item.reviewer_approved = decision.approved
        item.status = WorkspaceStatus.completed if decision.approved else WorkspaceStatus.blocked
        item.audit_log.append(f"Reviewer approval: {decision.approved}. {decision.reason}".strip())
        self._touch(item)
        message = "Workspace is ready for an explicitly approved merge" if decision.approved else "Workspace blocked by reviewer"
        return WorkspaceResult(success=decision.approved, message=message, workspace=item)

    @classmethod
    def _validate_patch(cls, patch: WorkspacePatch) -> None:
        seen: set[str] = set()
        for change in patch.changes:
            normalized = change.path.strip("/")
            if not normalized or normalized.startswith("..") or "/../" in normalized:
                raise WorkspaceError("Unsafe file path")
            if any(part.lower() in cls.PROTECTED_PATHS for part in normalized.split("/")):
                raise WorkspaceError("Protected file path")
            if normalized in seen:
                raise WorkspaceError("Duplicate file change")
            seen.add(normalized)
            if change.operation != FileOperation.delete and change.content is None:
                raise WorkspaceError("Create and update operations require content")

    @staticmethod
    def _require_patch(item: WorkspaceRecord) -> None:
        if item.patch is None:
            raise WorkspaceError("Workspace patch is missing")

    @staticmethod
    def _touch(item: WorkspaceRecord) -> None:
        item.updated_at = datetime.now(timezone.utc)


workspace_executor_service = WorkspaceExecutorService()
