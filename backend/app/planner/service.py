from app.orchestrator.models import TaskCreate
from app.orchestrator.service import orchestrator_service

from .models import ExecutionPlan, PlanGoal, PlannedStep, WorkerPreference


class PlannerService:
    """Creates safe, reviewable execution plans without external model calls."""

    def create_plan(self, payload: PlanGoal) -> ExecutionPlan:
        workers = payload.preferred_workers or [
            WorkerPreference.claude,
            WorkerPreference.codex,
            WorkerPreference.cursor,
            WorkerPreference.openai,
            WorkerPreference.gemini,
        ]

        architecture = PlannedStep(
            sequence=1,
            title="Define architecture and acceptance criteria",
            description=f"Design the solution for: {payload.goal}",
            required_capabilities=["architecture", "requirements"],
            preferred_worker=self._pick(workers, WorkerPreference.claude),
            priority=95,
        )
        implementation = PlannedStep(
            sequence=2,
            title="Implement core functionality",
            description="Build the smallest complete implementation that satisfies the acceptance criteria.",
            required_capabilities=["coding", "python"],
            preferred_worker=self._pick(workers, WorkerPreference.codex),
            priority=90,
            depends_on=[architecture.id],
        )
        tests = PlannedStep(
            sequence=3,
            title="Add automated tests",
            description="Cover successful flows, validation failures, safety constraints, and regressions.",
            required_capabilities=["testing", "python"],
            preferred_worker=self._pick(workers, WorkerPreference.cursor),
            priority=85,
            depends_on=[implementation.id],
        )
        review = PlannedStep(
            sequence=4,
            title="Review security and quality",
            description="Review architecture, code quality, secrets handling, permissions, and failure modes.",
            required_capabilities=["review", "security"],
            preferred_worker=self._pick(workers, WorkerPreference.gemini),
            priority=80,
            depends_on=[tests.id],
        )
        release = PlannedStep(
            sequence=5,
            title="Prepare release and documentation",
            description="Document setup, configuration, operating limits, rollback, and verification steps.",
            required_capabilities=["documentation", "release"],
            preferred_worker=self._pick(workers, WorkerPreference.openai),
            priority=70,
            depends_on=[review.id],
            approval_required=True,
            approval_reason="Deployment or production activation requires human approval.",
        )

        plan = ExecutionPlan(
            goal=payload.goal,
            summary="Five-stage plan: architecture, implementation, tests, review, and approved release.",
            steps=[architecture, implementation, tests, review, release],
        )

        if payload.create_tasks:
            plan.created_task_ids = [
                orchestrator_service.create_task(
                    TaskCreate(
                        title=step.title,
                        description=self._task_description(step),
                        priority=step.priority,
                        required_capabilities=step.required_capabilities,
                    )
                ).id
                for step in plan.steps
            ]
        return plan

    @staticmethod
    def _pick(
        workers: list[WorkerPreference], preferred: WorkerPreference
    ) -> WorkerPreference:
        return preferred if preferred in workers else workers[0]

    @staticmethod
    def _task_description(step: PlannedStep) -> str:
        dependency_text = ", ".join(str(item) for item in step.depends_on) or "none"
        approval_text = step.approval_reason if step.approval_required else "not required"
        return (
            f"{step.description}\n"
            f"Preferred worker: {step.preferred_worker.value}\n"
            f"Dependencies: {dependency_text}\n"
            f"Approval: {approval_text}"
        )


planner_service = PlannerService()
