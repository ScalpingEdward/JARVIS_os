from fastapi import APIRouter

from app.schemas.phoenix_demo1_memory_binding_v21_229 import MemoryContextQuery, MemoryContextResponse
from app.services.phoenix_demo1_memory_binding_v21_229 import memory_binding_status, retrieve_memory_context

router = APIRouter(prefix='/phoenix/demo1/v21.229/memory', tags=['phoenix-demo1-v21.229'])


@router.get('/status')
def status() -> dict:
    return memory_binding_status()


@router.post('/context', response_model=MemoryContextResponse)
def context(req: MemoryContextQuery) -> MemoryContextResponse:
    return retrieve_memory_context(req)
