from datetime import datetime, timezone
from uuid import UUID

from app.workspace.service import WorkspaceError, workspace_executor_service

from .models import SandboxResultIn, SandboxRunCreate, SandboxRunRecord, SandboxStatus


class SandboxError(ValueError):
    pass


class SandboxService:
    """Control plane for an external isolated runner.

    The API process never invokes a shell or Docker directly. A separate runner
    claims queued jobs, executes them in a restricted container, and reports the
    result through `complete`.
    """

    ALLOWED_IMAGES = {"python:3.11-slim", "python:3.12-slim", "node:20-alpine"}
    BLOCKED_TOKENS = {"sudo", "docker", "podman", "--privileged", "/var/run/docker.sock"}

    def __init__(self) -> None:
        self._runs: dict[UUID, SandboxRunRecord] = {}

    def reset(self) -> None:
        self._runs.clear()

    def create(self, payload: SandboxRunCreate) -> SandboxRunRecord:
        workspace = workspace_executor_service.get(payload.workspace_id)
        if not workspace.approved:
            raise SandboxError("Workspace requires human approval")
        if workspace.patch is None:
            raise SandboxError("Workspace patch is missing")
        if payload.repository != workspace.repository:
            raise SandboxError("Repository does not match workspace")
        if payload.image not in self.ALLOWED_IMAGES:
            raise SandboxError("Sandbox image is not allowlisted")
        command = payload.test_command.lower()
        if any(token in command for token in self.BLOCKED_TOKENS):
            raise SandboxError("Unsafe test command")
        if payload.network_enabled:
            raise SandboxError("Network access is disabled for test sandboxes")
        run = SandboxRunRecord(**payload.model_dump())
        self._runs[run.id] = run
        return run

    def list_all(self) -> list[SandboxRunRecord]:
        return sorted(self._runs.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, run_id: UUID) -> SandboxRunRecord:
        run = self._runs.get(run_id)
        if run is None:
            raise SandboxError("Sandbox run not found")
        return run

    def claim(self, run_id: UUID) -> SandboxRunRecord:
        run = self.get(run_id)
        if run.status != SandboxStatus.queued:
            raise SandboxError("Sandbox run is not queued")
        run.status = SandboxStatus.running
        run.started_at = datetime.now(timezone.utc)
        return run

    def claim_next(self) -> SandboxRunRecord | None:
        queued = sorted(
            (run for run in self._runs.values() if run.status == SandboxStatus.queued),
            key=lambda item: item.created_at,
        )
        if not queued:
            return None
        return self.claim(queued[0].id)

    def complete(self, run_id: UUID, result: SandboxResultIn) -> SandboxRunRecord:
        run = self.get(run_id)
        if run.status != SandboxStatus.running:
            raise SandboxError("Sandbox run is not running")
        run.exit_code = result.exit_code
        run.stdout = result.stdout
        run.stderr = result.stderr
        run.finished_at = datetime.now(timezone.utc)
        if result.timed_out:
            run.status = SandboxStatus.timed_out
            run.failure_summary = "Sandbox exceeded its execution timeout"
        elif result.exit_code == 0:
            run.status = SandboxStatus.passed
        else:
            run.status = SandboxStatus.failed
            run.failure_summary = self._summarize_failure(result)
            run.fix_prompt = self._build_fix_prompt(run)
        details = run.failure_summary or "isolated sandbox green"
        try:
            workspace_executor_service.record_tests(run.workspace_id, run.status == SandboxStatus.passed, details)
        except WorkspaceError as exc:
            raise SandboxError(str(exc)) from exc
        return run

    @staticmethod
    def _summarize_failure(result: SandboxResultIn) -> str:
        source = result.stderr.strip() or result.stdout.strip() or "Tests failed without output"
        lines = [line for line in source.splitlines() if line.strip()]
        return "\n".join(lines[-20:])[:4000]

    @staticmethod
    def _build_fix_prompt(run: SandboxRunRecord) -> str:
        return (
            "Fix the failing tests in the prepared workspace. Do not change protected files, "
            "do not weaken tests, and return a minimal patch. Failure output:\n" + (run.failure_summary or "")
        )


sandbox_service = SandboxService()
