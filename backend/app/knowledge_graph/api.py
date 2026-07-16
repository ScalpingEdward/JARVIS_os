from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import EdgeCreate, EdgeRecord, GraphReasonRequest, GraphReasonResponse, GraphStatus, NodeCreate, NodeRecord
from .service import knowledge_graph_service

router = APIRouter(prefix="/v1/knowledge-graph", tags=["knowledge-graph"])


@router.get("/status", response_model=GraphStatus)
def graph_status() -> GraphStatus:
    return knowledge_graph_service.status()


@router.post("/nodes", response_model=NodeRecord, status_code=status.HTTP_201_CREATED)
def create_node(payload: NodeCreate) -> NodeRecord:
    return knowledge_graph_service.create_node(payload)


@router.get("/nodes/search", response_model=list[NodeRecord])
def search_nodes(q: str = Query(min_length=1, max_length=300), kind: str | None = None) -> list[NodeRecord]:
    return knowledge_graph_service.search_nodes(q, kind)


@router.get("/nodes/{node_id}", response_model=NodeRecord)
def get_node(node_id: UUID) -> NodeRecord:
    node = knowledge_graph_service.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.post("/edges", response_model=EdgeRecord, status_code=status.HTTP_201_CREATED)
def create_edge(payload: EdgeCreate) -> EdgeRecord:
    try:
        return knowledge_graph_service.create_edge(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/nodes/{node_id}/neighbors")
def neighbors(node_id: UUID, direction: str = Query(default="both", pattern="^(in|out|both)$")) -> list[dict]:
    return knowledge_graph_service.neighbors(node_id, direction)


@router.get("/paths")
def paths(source_id: UUID, target_id: UUID, max_depth: int = Query(default=5, ge=1, le=8)):
    return knowledge_graph_service.paths(source_id, target_id, max_depth)


@router.get("/nodes/{node_id}/similar")
def similar(node_id: UUID, limit: int = Query(default=10, ge=1, le=50)) -> list[dict]:
    return knowledge_graph_service.similar(node_id, limit)


@router.post("/reason", response_model=GraphReasonResponse)
def reason(payload: GraphReasonRequest) -> GraphReasonResponse:
    return knowledge_graph_service.reason(payload)
