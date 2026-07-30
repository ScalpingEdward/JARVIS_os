from fastapi.testclient import TestClient

from app.main import app
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service
from app.schemas.phoenix_demo1_memory_binding_v21_229 import MemoryContextQuery
from app.services.phoenix_demo1_memory_binding_v21_229 import memory_binding_status, retrieve_memory_context


def setup_function():
    memory_service.reset()


def test_memory_binding_status_is_live():
    status = memory_binding_status()
    assert status['provider_bound'] is True
    assert status['context_retrieval_enabled'] is True
    assert status['autonomous_memory_mutation_enabled'] is False


def test_context_retrieval_returns_ranked_memory():
    memory_service.create(MemoryCreate(content='Gold trading plan uses XAUUSD London session context.', category='trading', priority=MemoryPriority.high, tags=['gold','xauusd']))
    memory_service.create(MemoryCreate(content='Generic note.', category='general', priority=MemoryPriority.low))
    result = retrieve_memory_context(MemoryContextQuery(query='gold xauusd', category='trading'))
    assert result.state == 'ready'
    assert result.context_available is True
    assert result.count == 1
    assert result.items[0].category == 'trading'


def test_min_priority_filters_memory():
    memory_service.create(MemoryCreate(content='gold note', priority=MemoryPriority.low))
    result = retrieve_memory_context(MemoryContextQuery(query='gold', min_priority=3))
    assert result.state == 'empty'


def test_content_can_be_redacted_from_response():
    memory_service.create(MemoryCreate(content='private demo context', priority=MemoryPriority.high))
    result = retrieve_memory_context(MemoryContextQuery(query='private', include_content=False))
    assert result.items[0].content is None


def test_risk_brain_blocks_context_release():
    memory_service.create(MemoryCreate(content='gold context', priority=MemoryPriority.high))
    result = retrieve_memory_context(MemoryContextQuery(query='gold', risk_brain_hard_block=True))
    assert result.state == 'blocked'
    assert result.items == []


def test_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.229/memory/status' in paths
    assert '/phoenix/demo1/v21.229/memory/context' in paths


def test_context_endpoint():
    memory_service.create(MemoryCreate(content='demo memory binding context', priority=MemoryPriority.high))
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.229/memory/context', json={'query':'demo memory'})
    assert response.status_code == 200
    assert response.json()['provider_bound'] is True
