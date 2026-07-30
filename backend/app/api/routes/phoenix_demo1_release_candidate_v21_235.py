from fastapi import APIRouter

from app.schemas.phoenix_demo1_release_candidate_v21_235 import ReleaseCandidateRequest, ReleaseCandidateResult
from app.services.phoenix_demo1_release_candidate_v21_235 import build_release_candidate

router = APIRouter(prefix='/phoenix/demo1/v21.235', tags=['phoenix-demo1-v21.235'])


@router.post('/release-candidate', response_model=ReleaseCandidateResult)
def release_candidate(req: ReleaseCandidateRequest):
    return build_release_candidate(req)
