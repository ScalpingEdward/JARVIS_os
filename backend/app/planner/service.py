from copy import deepcopy
from uuid import UUID

from app.orchestrator.models import TaskCreate
from app.orchestrator.service import orchestrator_service

from .models import (
    ExecutionPlan,
    PlanGoal,
    PlanProgressResponse,
    PlanStatus,
    PlannedStep,
    StepStatus,
    WorkerPreference,
)


class PlannerError(ValueError):
    pass


class PlannerService:
    """Builds reviewable project graphs and tracks dependency-aware execution."""

    def __init__(self) -> None:
        self._plans: dict[UUID, ExecutionPlan] = {}

    def reset(self) -> None:
        self._plans.clear()

    def create_plan(self, payload: PlanGoal) -> ExecutionPlan:
        workers = payload.preferred_workers or [
            WorkerPreference.claude,
            WorkerPreference.codex,
            WorkerPreference.gemini,
            WorkerPreference.openai,
        ]

        discovery = self._step(
            1,
            "Discovery",
            "Analyse goal, constraints and acceptance criteria",
            f"Turn the project goal into explicit functional, safety and operational requirements: {payload.goal}",
            ["requirements specification", "risk register", "acceptance criteria"],
            ["all user constraints are represented", "unknowns and approval points are explicit"],
            ["requirements", "architecture"],
            self._pick(workers, WorkerPreference.claude),
            self._pick(workers, WorkerPreference.gemini),
            100,
        )
        architecture = self._step(
            2,
            "Architecture",
            "Design system architecture and interfaces",
            "Define modules, data contracts, security boundaries, persistence and integration points.",
            ["architecture decision record", "module map", "API and data contracts"],
            ["components have clear ownership", "failure and rollback paths are defined"],
            ["architecture", "security"],
            self._pick(workers, WorkerPreference.claude),
            self._pick(workers, WorkerPreference.openai),
            95,
            [discovery.id],
        )
        backend = self._step(
            3,
            "Implementation",
            "Implement backend and core domain logic",
            "Build the smallest complete backend implementation behind existing approval and safety gates.",
            ["domain services", "API endpoints", "persistence integration"],
            ["core flows execute end to end", "unsafe actions remain gated"],
            ["coding", "python", "backend"],
            self._pick(workers, WorkerPreference.codex),
            self._pick(workers, WorkerPreference.claude),
            90,
            [architecture.id],
        )
        steps = [discovery, architecture, backend]

        if payload.include_frontend:
            frontend = self._step(
                len(steps) + 1,
                "Implementation",
                "Build operator interface",
                "Create a usable control surface for project state, approvals, agent assignments and failures.",
                ["responsive interface", "project dashboard", "approval controls"],
                ["critical state is visible", "dangerous actions require explicit confirmation"],
                ["frontend", "ux"],
                self._pick(workers, WorkerPreference.openai),
                self._pick(workers, WorkerPreference.gemini),
                82,
                [architecture.id],
            )
            steps.append(frontend)

        test_dependencies = [step.id for step in steps if step.phase == "Implementation"]
        tests = self._step(
            len(steps) + 1,
            "Verification",
            "Add automated and integration tests",
            "Verify happy paths, dependency ordering, validation, permissions, retries and regressions.",
            ["unit tests", "integration tests", "security regression tests"],
            ["all required checks pass", "tests do not bypass approval controls"],
            ["testing", "quality"],
            self._pick(workers, WorkerPreference.codex),
            self._pick(workers, WorkerPreference.gemini),
            88,
            test_dependencies,
        )
        review = self._step(
            len(steps) + 2,
            "Review",
            "Run independent security and quality review",
            "Review code, architecture, secrets handling, permissions, observability and operational failure modes.",
            ["review report", "resolved findings", "release recommendation"],
            ["no unresolved critical finding", "reviewer differs from primary implementer"],
            ["review", "security"],
            self._pick(workers, WorkerPreference.gemini),
            self._pick(workers, WorkerPreference.claude),
            84,
            [tests.id],
        )
        steps.extend([tests, review])

        if payload.include_documentation:
            documentation = self._step(
                len(steps) + 1,
                "Release",
                "Prepare operating documentation",
                "Document setup, configuration, credentials, limits, backup, recovery and troubleshooting.",
                ["operator guide", "configuration reference", "recovery runbook"],
                ["a new operator can deploy safely", "no secrets appear in documentation"],
                ["documentation", "operations"],
                self._pick(workers, WorkerPreference.openai),
                self._pick(workers, WorkerPreference.claude),
                70,
                [review.id],
            )
            steps.append(documentation)

        if payload.include_deployment:
            release_dependency = steps[-1].id
            deployment = self._step(
                len(steps) + 1,
                "Release",
                "Prepare approved deployment",
                "Create a reversible deployment plan and stop before production activation until human approval.",
                ["deployment manifest", "health verification", "rollback procedure"],
                ["sandbox and CI are green", "rollback is tested", "human approval is recorded"],
                ["deployment", "operations"],
                self._pick(workers, WorkerPreference.codex),
                self._pick(workers, WorkerPreference.gemini),
                65,
                [release_dependency],
                True,
                "Production deployment requires explicit human approval.",
            )
            steps.append(deployment)

        steps[0].status = StepStatus.ready
        plan = ExecutionPlan(
            goal=payload.goal,
            summary=f"Dependency-aware multi-agent plan with {len(steps)} steps and independent reviews.",
            constraints=payload.constraints,
            status=PlanStatus.ready,
            steps=steps,
        )
        if payload.create_tasks:
            for step in plan.steps:
                task = orchestrator_service.create_task(
                    TaskCreate(
                        title=step.title,
                        description=self._task_description(step),
                        priority=step.priority,
                        required_capabilities=step.required_capabilities,
                    )
                )
                step.orchestrator_task_id = task.id
                plan.created_task_ids.append(task.id)
        self._plans[plan.id] = plan
        return deepcopy(plan)

    def list_plans(self) -> list[ExecutionPlan]:
        return [deepcopy(item) for item in self._plans.values()]

    def get(self, plan_id: UUID) -> ExecutionPlan:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise PlannerError("Plan not found")
        return deepcopy(plan)

    def update_step(self, plan_id: UUID, step_id: UUID, status: StepStatus) -> ExecutionPlan:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise PlannerError("Plan not found")
        step = next((item for item in plan.steps if item.id == step_id), None)
        if step is None:
            raise PlannerError("Planning step not found")
        if status in {StepStatus.in_progress, StepStatus.review, StepStatus.completed}:
            incomplete = [dependency for dependency in step.depends_on if self._step_by_id(plan, dependency).status != StepStatus.completed]
            if incomplete:
                raise PlannerError("Step dependencies are not completed")
        step.status = status
        self._refresh(plan)
        return deepcopy(plan)

    def progress(self, plan_id: UUID) -> PlanProgressResponse:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise PlannerError("Plan not found")
        completed = sum(step.status == StepStatus.completed for step in plan.steps)
        ready = [step.id for step in plan.steps if step.status == StepStatus.ready]
        blocked = [step.id for step in plan.steps if step.status == StepStatus.blocked]
        return PlanProgressResponse(
            plan_id=plan.id,
            status=plan.status,
            total_steps=len(plan.steps),
            completed_steps=completed,
            ready_steps=ready,
            blocked_steps=blocked,
            progress_percent=round(completed * 100 / len(plan.steps)),
        )

    def _refresh(self, plan: ExecutionPlan) -> None:
        for step in plan.steps:
            if step.status == StepStatus.pending and all(
                self._step_by_id(plan, dependency).status == StepStatus.completed for dependency in step.depends_on
            ):
                step.status = StepStatus.ready
        if all(step.status == StepStatus.completed for step in plan.steps):
            plan.status = PlanStatus.completed
        elif any(step.status in {StepStatus.in_progress, StepStatus.review} for step in plan.steps):
            plan.status = PlanStatus.active
        elif any(step.status in {StepStatus.blocked, StepStatus.failed} for step in plan.steps):
            plan.status = PlanStatus.blocked
        else:
            plan.status = PlanStatus.ready

    @staticmethod
    def _step_by_id(plan: ExecutionPlan, step_id: UUID) -> PlannedStep:
        return next(step for step in plan.steps if step.id == step_id)

    @staticmethod
    def _step(
        sequence: int,
        phase: str,
        title: str,
        description: str,
        deliverables: list[str],
        acceptance_criteria: list[str],
        capabilities: list[str],
        worker: WorkerPreference,
        reviewer: WorkerPreference,
        priority: int,
        dependencies: list[UUID] | None = None,
        approval_required: bool = False,
        approval_reason: str | None = None,
    ) -> PlannedStep:
        return PlannedStep(
            sequence=sequence,
            phase=phase,
            title=title,
            description=description,
            deliverables=deliverables,
            acceptance_criteria=acceptance_criteria,
            required_capabilities=capabilities,
            preferred_worker=worker,
            reviewer_worker=reviewer,
            priority=priority,
            depends_on=dependencies or [],
            approval_required=approval_required,
            approval_reason=approval_reason,
        )

    @staticmethod
    def _pick(workers: list[WorkerPreference], preferred: WorkerPreference) -> WorkerPreference:
        return preferred if preferred in workers else workers[0]

    @staticmethod
    def _task_description(step: PlannedStep) -> str:
        dependencies = ", ".join(str(item) for item in step.depends_on) or "none"
        return (
            f"{step.description}\n"
            f"Phase: {step.phase}\n"
            f"Primary agent: {step.preferred_worker.value}\n"
            f"Reviewer: {step.reviewer_worker.value if step.reviewer_worker else 'none'}\n"
            f"Dependencies: {dependencies}\n"
            f"Deliverables: {'; '.join(step.deliverables)}\n"
            f"Acceptance criteria: {'; '.join(step.acceptance_criteria)}\n"
            f"Approval: {step.approval_reason or 'not required'}"
        )


planner_service = PlannerService()
