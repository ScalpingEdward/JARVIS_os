from app.memory.models import MemoryCreate
from app.memory.service import MemoryService
from app.memory.sql_storage import SQLMemoryStore
from app.orchestrator.models import AgentCreate, TaskCreate
from app.orchestrator.service import OrchestratorService


def test_memory_survives_service_reconstruction() -> None:
    first = MemoryService(SQLMemoryStore())
    first.reset()
    created = first.create(
        MemoryCreate(
            content="Persistent JARVIS memory",
            category="project",
            tags=["jarvis"],
            priority=4,
        )
    )

    second = MemoryService(SQLMemoryStore())
    items = second.list_all()
    assert any(item.id == created.id for item in items)


def test_tasks_and_agents_survive_service_reconstruction() -> None:
    first = OrchestratorService()
    first.reset()
    agent = first.register_agent(
        AgentCreate(name="Persistent Worker", role="developer", capabilities=["python"])
    )
    task = first.create_task(
        TaskCreate(
            title="Persistent task",
            description="Must survive service reconstruction",
            required_capabilities=["python"],
        )
    )
    assigned = first.assign_next()
    assert assigned is not None

    second = OrchestratorService()
    agents = second.list_agents()
    tasks = second.list_tasks()
    assert any(item.id == agent.id for item in agents)
    assert any(item.id == task.id and item.assigned_agent_id == agent.id for item in tasks)
