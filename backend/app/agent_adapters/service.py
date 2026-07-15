from uuid import UUID

from app.collaboration.models import AgentRole, ContributionCreate, ReviewCreate
from app.collaboration.service import CollaborationError, CollaborationService, collaboration_service
from app.models.contracts import ModelRequest
from app.models.router import ModelRouter, UnknownProviderError, model_router
from app.runtime.models import RunStatus, RuntimeRunCreate, RuntimeRunUpdate
from app.runtime.service import AgentRuntimeService, agent_runtime_service

from .models import AdapterExecutionResult, AgentAdapterDescriptor, ContributionDispatch, ReviewDispatch


class AgentAdapterError(ValueError):
    pass


class AgentAdapterService:
    PROVIDER_ALIASES = {
        "claude": "anthropic",
        "anthropic": "anthropic",
        "gpt": "openai",
        "openai": "openai",
        "codex": "openai",
        "gemini": "gemini",
        "mock": "mock",
    }

    def __init__(
        self,
        router: ModelRouter = model_router,
        collaborations: CollaborationService = collaboration_service,
        runtime: AgentRuntimeService = agent_runtime_service,
    ) -> None:
        self._router = router
        self._collaborations = collaborations
        self._runtime = runtime

    def list_adapters(self) -> list[AgentAdapterDescriptor]:
        available = set(self._router.available_providers())
        return [
            AgentAdapterDescriptor(
                provider=name,
                model_provider=model_provider,
                available=model_provider in available,
            )
            for name, model_provider in sorted(self.PROVIDER_ALIASES.items())
        ]

    def dispatch_contribution(self, payload: ContributionDispatch) -> AdapterExecutionResult:
        session = self._collaborations.get(payload.session_id)
        participant = self._participant(session, payload.participant_name)
        if participant.role in {AgentRole.reviewer, AgentRole.decision_maker}:
            raise AgentAdapterError("Reviewer roles cannot submit implementation contributions")
        provider = self._resolve_provider(participant.provider)
        run = self._runtime.create_run(
            RuntimeRunCreate(
                title=f"{participant.name}: {session.title}",
                payload={"session_id": str(session.id), "participant": participant.name, "mode": "contribution"},
                required_capabilities=[participant.role.value],
            )
        )
        run.status = RunStatus.running
        run.attempt = 1
        prompt = self._contribution_prompt(session.objective, participant.role.value, payload.instructions)
        try:
            response = self._router.generate(ModelRequest(prompt=prompt, task_type=participant.role.value), provider_name=provider)
            updated = self._collaborations.contribute(
                session.id,
                ContributionCreate(
                    participant_name=participant.name,
                    content=response.content,
                    artifacts=payload.artifacts,
                ),
            )
            contribution = updated.contributions[-1]
            self._runtime.update_run(run.id, RuntimeRunUpdate(status=RunStatus.completed, output=response.content))
            return AdapterExecutionResult(
                provider=response.provider,
                model=response.model,
                runtime_run_id=run.id,
                session_id=session.id,
                contribution_id=contribution.id,
                content=response.content,
            )
        except (UnknownProviderError, CollaborationError, Exception) as exc:
            self._runtime.update_run(run.id, RuntimeRunUpdate(status=RunStatus.failed, error=str(exc)))
            if isinstance(exc, AgentAdapterError):
                raise
            raise AgentAdapterError(str(exc)) from exc

    def dispatch_review(self, payload: ReviewDispatch) -> AdapterExecutionResult:
        session = self._collaborations.get(payload.session_id)
        reviewer = self._participant(session, payload.reviewer_name)
        if reviewer.role not in {AgentRole.reviewer, AgentRole.decision_maker}:
            raise AgentAdapterError("Participant is not allowed to review")
        contribution = self._contribution(session, payload.contribution_id)
        provider = self._resolve_provider(reviewer.provider)
        run = self._runtime.create_run(
            RuntimeRunCreate(
                title=f"Review by {reviewer.name}: {session.title}",
                payload={"session_id": str(session.id), "contribution_id": str(contribution.id), "mode": "review"},
                required_capabilities=["review"],
            )
        )
        run.status = RunStatus.running
        run.attempt = 1
        prompt = self._review_prompt(session.objective, contribution.content, payload.instructions)
        try:
            response = self._router.generate(ModelRequest(prompt=prompt, task_type="review"), provider_name=provider)
            approved = response.content.lstrip().upper().startswith("APPROVE")
            self._collaborations.review(
                session.id,
                contribution.id,
                ReviewCreate(reviewer_name=reviewer.name, approved=approved, comments=response.content),
            )
            self._runtime.update_run(run.id, RuntimeRunUpdate(status=RunStatus.completed, output=response.content))
            return AdapterExecutionResult(
                provider=response.provider,
                model=response.model,
                runtime_run_id=run.id,
                session_id=session.id,
                contribution_id=contribution.id,
                approved=approved,
                content=response.content,
            )
        except (UnknownProviderError, CollaborationError, Exception) as exc:
            self._runtime.update_run(run.id, RuntimeRunUpdate(status=RunStatus.failed, error=str(exc)))
            raise AgentAdapterError(str(exc)) from exc

    def _resolve_provider(self, provider: str) -> str:
        resolved = self.PROVIDER_ALIASES.get(provider.lower(), provider.lower())
        if resolved not in self._router.available_providers():
            raise AgentAdapterError(f"Model provider is not configured: {resolved}")
        return resolved

    @staticmethod
    def _participant(session, name: str):
        for participant in session.participants:
            if participant.name == name:
                return participant
        raise AgentAdapterError("Participant not found")

    @staticmethod
    def _contribution(session, contribution_id: UUID):
        for contribution in session.contributions:
            if contribution.id == contribution_id:
                return contribution
        raise AgentAdapterError("Contribution not found")

    @staticmethod
    def _contribution_prompt(objective: str, role: str, instructions: str) -> str:
        return (
            "You are a JARVIS collaboration agent. Produce a concrete, reviewable result.\n"
            f"Role: {role}\nObjective: {objective}\nAdditional instructions: {instructions or 'None'}\n"
            "Do not claim actions you did not perform. Return the proposed result only."
        )

    @staticmethod
    def _review_prompt(objective: str, contribution: str, instructions: str) -> str:
        return (
            "Review the contribution against the objective. Start the response with exactly APPROVE or REJECT, "
            "then explain the decision and list required corrections.\n"
            f"Objective: {objective}\nContribution:\n{contribution}\nAdditional instructions: {instructions or 'None'}"
        )


agent_adapter_service = AgentAdapterService()
