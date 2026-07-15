from datetime import datetime, timezone
from uuid import UUID

from app.sandbox.models import SandboxRunCreate, SandboxStatus
from app.sandbox.service import SandboxError, sandbox_service
from app.workspace.models import WorkspacePatch
from app.workspace.service import WorkspaceError, workspace_executor_service

from .models import AutoFixCreate, AutoFixPatch, AutoFixRecord, AutoFixStatus


class AutoFixError(ValueError):
    pass


class AutoFixService:
    """Bounded control loop between failed sandbox tests and a coding agent.

    The service never executes code, mutates GitHub, or merges a pull request.
    It records the next Codex prompt, accepts an approved replacement patch,
    and queues another isolated sandbox run. Remote execution remains gated by
    the existing workspace and GitHub executor services.
    """

    def __init__(self) -> None:
        self._items: dict[UUID, AutoFixRecord] = {}

    def reset(self) -> None:
        self._items.clear()

    def create(self, payload: AutoFixCreate) -> AutoFixRecord:
        workspace = workspace_executor_service.get(payload.workspace_id)
        if not workspace.approved or workspace.patch is None:
            raise AutoFixError("Approved workspace with a prepared patch is required")
        item = AutoFixRecord(workspace_id=payload.workspace_id, max_attempts=payload.max_attempts)
        item.audit_log.append("Auto-fix loop created")
        self._items[item.id] = item
        return item

    def list_all(self) -> list[AutoFixRecord]:
        return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, loop_id: UUID) -> AutoFixRecord:
        item = self._items.get(loop_id)
        if item is None:
            raise AutoFixError("Auto-fix loop not found")
        return item

    def ingest_sandbox_result(self, loop_id: UUID, run_id: UUID) -> AutoFixRecord:
        item = self.get(loop_id)
        run = sandbox_service.get(run_id)
        if run.workspace_id != item.workspace_id:
            raise AutoFixError("Sandbox run belongs to another workspace")
        if run.status == SandboxStatus.passed:
            item.status = AutoFixStatus.succeeded
            item.last_sandbox_run_id = run.id
            item.audit_log.append("Sandbox passed; remote execution gate is open")
            return self._touch(item)
        if run.status not in {SandboxStatus.failed, SandboxStatus.timed_out}:
            raise AutoFixError("Sandbox run is not complete")
        item.attempts += 1
        item.last_sandbox_run_id = run.id
        item.last_failure = run.failure_summary or "Tests failed"
        if item.attempts >= item.max_attempts:
            item.status = AutoFixStatus.escalated
            item.escalation_reason = f"Maximum fix attempts reached ({item.max_attempts})"
            item.audit_log.append(item.escalation_reason)
        else:
            item.status = AutoFixStatus.awaiting_patch
            item.fix_prompt = run.fix_prompt or self._fallback_prompt(item.last_failure, item.attempts)
            item.audit_log.append(f"Fix attempt {item.attempts} requested")
        return self._touch(item)

    def apply_patch_and_retry(self, loop_id: UUID, patch: WorkspacePatch, metadata: AutoFixPatch) -> AutoFixRecord:
        item = self.get(loop_id)
        if item.status != AutoFixStatus.awaiting_patch:
            raise AutoFixError("Loop is not awaiting a patch")
        if metadata.attempt != item.attempts:
            raise AutoFixError("Patch attempt does not match the active attempt")
        try:
            workspace_executor_service.attach_patch(item.workspace_id, patch)
            workspace = workspace_executor_service.get(item.workspace_id)
            run = sandbox_service.create(
                SandboxRunCreate(
                    workspace_id=workspace.id,
                    repository=workspace.repository,
                    ref=workspace.branch_name,
                    test_command=workspace.test_command,
                )
            )
        except (WorkspaceError, SandboxError) as exc:
            raise AutoFixError(str(exc)) from exc
        item.patch_summary = metadata.summary
        item.last_sandbox_run_id = run.id
        item.status = AutoFixStatus.testing
        item.audit_log.append(f"Replacement patch accepted; sandbox run queued: {run.id}")
        return self._touch(item)

    @staticmethod
    def _fallback_prompt(failure: str, attempt: int) -> str:
        return (
            f"Auto-fix attempt {attempt}: diagnose the failing tests and return a minimal WorkspacePatch. "
            "Do not weaken tests, touch protected paths, add secrets, or broaden scope. Failure:\n" + failure
        )

    @staticmethod
    def _touch(item: AutoFixRecord) -> AutoFixRecord:
        item.updated_at = datetime.now(timezone.utc)
        return item


autofix_service = AutoFixService()
