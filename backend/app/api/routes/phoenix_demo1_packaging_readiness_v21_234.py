from fastapi import APIRouter

from app.schemas.phoenix_demo1_packaging_readiness_v21_234 import PackagingReadinessRequest, PackagingReadinessResult
from app.services.phoenix_demo1_packaging_readiness_v21_234 import build_packaging_readiness

router = APIRouter(prefix='/phoenix/demo1/v21.234', tags=['phoenix-demo1-v21.234'])


@router.post('/packaging-readiness', response_model=PackagingReadinessResult)
def packaging_readiness(req: PackagingReadinessRequest):
    return build_packaging_readiness(req)
