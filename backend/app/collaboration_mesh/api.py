from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    AgentContribution,
    CollaborationMission,
    ConsensusVote,
    MeshAgent,
    MeshAgentCreate,
    MeshStatus,
    MissionCreate,
)
from .service import collaboration_mesh_service

router = APIRouter(prefix="/v1/collaboration-mesh", tags=["collaboration-mesh"])


@router.get("/status", response_model=MeshStatus)
def mesh_status() -> MeshStatus:
    return collaboration_mesh_service.status()


@router.post("/agents", response_model=MeshAgent, status_code=status.HTTP_201_CREATED)
def register_agent(payload: MeshAgentCreate) -> MeshAgent:
    return collaboration_mesh_service.register_agent(payload)


@router.get("/agents", response_model=list[MeshAgent])
def list_agents() -> list[MeshAgent]:
    return collaboration_mesh_service.agents()


@router.post("/missions", response_model=CollaborationMission, status_code=status.HTTP_201_CREATED)
def create_mission(payload: MissionCreate) -> CollaborationMission:
    return collaboration_mesh_service.create_mission(payload)


@router.get("/missions", response_model=list[CollaborationMission])
def list_missions() -> list[CollaborationMission]:
    return collaboration_mesh_service.missions()


@router.get("/missions/{mission_id}", response_model=CollaborationMission)
def get_mission(mission_id: UUID) -> CollaborationMission:
    mission = collaboration_mesh_service.get_mission(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Collaboration mission not found")
    return mission


@router.post("/missions/{mission_id}/contributions", response_model=CollaborationMission)
def add_contribution(mission_id: UUID, payload: AgentContribution) -> CollaborationMission:
    mission = collaboration_mesh_service.contribute(mission_id, payload)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission or assigned agent not found")
    return mission


@router.post("/missions/{mission_id}/votes", response_model=CollaborationMission)
def add_vote(mission_id: UUID, payload: ConsensusVote) -> CollaborationMission:
    mission = collaboration_mesh_service.vote(mission_id, payload)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission or assigned agent not found")
    return mission
