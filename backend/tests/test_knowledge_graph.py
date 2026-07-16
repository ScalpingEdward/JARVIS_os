from app.knowledge_graph.models import EdgeCreate, EdgeKind, GraphReasonRequest, NodeCreate, NodeKind
from app.knowledge_graph.service import knowledge_graph_service


def setup_function() -> None:
    knowledge_graph_service.reset()


def test_graph_paths_and_neighbors() -> None:
    gold = knowledge_graph_service.create_node(NodeCreate(name="XAUUSD", kind=NodeKind.market, tags={"gold", "trading"}))
    london = knowledge_graph_service.create_node(NodeCreate(name="London Session", kind=NodeKind.session, tags={"trading", "session"}))
    sweep = knowledge_graph_service.create_node(NodeCreate(name="Liquidity Sweep", kind=NodeKind.setup, tags={"trading", "liquidity"}))
    first = knowledge_graph_service.create_edge(EdgeCreate(source_id=london.id, target_id=sweep.id, kind=EdgeKind.triggers, weight=0.9, confidence=0.9))
    knowledge_graph_service.create_edge(EdgeCreate(source_id=sweep.id, target_id=gold.id, kind=EdgeKind.affects, weight=0.8, confidence=0.9))

    neighbors = knowledge_graph_service.neighbors(london.id)
    assert neighbors[0]["edge"].id == first.id
    paths = knowledge_graph_service.paths(london.id, gold.id)
    assert paths
    assert paths[0].node_ids == [london.id, sweep.id, gold.id]


def test_similarity_and_reasoning_are_advisory() -> None:
    a = knowledge_graph_service.create_node(NodeCreate(name="Setup A", kind=NodeKind.setup, tags={"ict", "gold", "london"}))
    b = knowledge_graph_service.create_node(NodeCreate(name="Setup B", kind=NodeKind.setup, tags={"ict", "gold"}))
    knowledge_graph_service.create_edge(EdgeCreate(source_id=a.id, target_id=b.id, kind=EdgeKind.similar_to, confidence=0.95))

    similar = knowledge_graph_service.similar(a.id)
    assert similar[0]["node"].id == b.id
    result = knowledge_graph_service.reason(GraphReasonRequest(question="Which setup is related?", start_node_ids=[a.id]))
    assert result.advisory_only is True
    assert result.supporting_paths


def test_status_keeps_execution_disabled() -> None:
    status = knowledge_graph_service.status()
    assert status.automatic_order_execution is False
    assert status.automatic_merge is False
