from app.agent_adapters.models import ContributionDispatch, ReviewDispatch
from app.agent_adapters.service import AgentAdapterService
from app.collaboration.models import AgentRole, CollaborationCreate, Participant
from app.collaboration.service import CollaborationService
from app.models.contracts import ModelProvider, ModelRequest, ModelResponse
from app.models.router import ModelRouter
from app.runtime.service import AgentRuntimeService


class SequenceProvider(ModelProvider):
    name = "mock"

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs

    def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(provider=self.name, model="sequence-test", content=self.outputs.pop(0))


def build_service(outputs: list[str]):
    collaborations = CollaborationService()
    runtime = AgentRuntimeService()
    router = ModelRouter(providers=[SequenceProvider(outputs)])
    service = AgentAdapterService(router=router, collaborations=collaborations, runtime=runtime)
    session = collaborations.create(
        CollaborationCreate(
            title="Build parser",
            objective="Create and review a safe Telegram signal parser",
            participants=[
                Participant(name="Codex", provider="mock", role=AgentRole.implementer),
                Participant(name="Claude", provider="mock", role=AgentRole.reviewer),
            ],
            required_reviews=1,
        )
    )
    return service, collaborations, runtime, session


def test_adapter_creates_contribution_and_completed_runtime_run() -> None:
    service, collaborations, runtime, session = build_service(["Implementation proposal"])

    result = service.dispatch_contribution(
        ContributionDispatch(session_id=session.id, participant_name="Codex")
    )

    stored = collaborations.get(session.id)
    assert result.content == "Implementation proposal"
    assert stored.contributions[0].participant_name == "Codex"
    assert runtime.list_runs()[0].status == "completed"


def test_adapter_review_resolves_collaboration() -> None:
    service, collaborations, runtime, session = build_service(
        ["Implementation proposal", "APPROVE\nThe proposal meets the objective."]
    )
    contribution = service.dispatch_contribution(
        ContributionDispatch(session_id=session.id, participant_name="Codex")
    )

    review = service.dispatch_review(
        ReviewDispatch(
            session_id=session.id,
            contribution_id=contribution.contribution_id,
            reviewer_name="Claude",
        )
    )

    stored = collaborations.get(session.id)
    assert review.approved is True
    assert stored.status == "resolved"
    assert stored.selected_contribution_id == contribution.contribution_id
    assert len(runtime.list_runs()) == 2


def test_adapter_registry_reports_configured_aliases() -> None:
    service, _, _, _ = build_service([])
    adapters = {item.provider: item for item in service.list_adapters()}

    assert adapters["mock"].available is True
    assert adapters["codex"].model_provider == "openai"
    assert adapters["codex"].available is False
