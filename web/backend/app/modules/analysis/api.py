from fastapi import APIRouter, Depends

from app.contracts.dto import Actor
from app.modules.analysis.schemas import Capability
from app.modules.analysis.service import AnalysisService


def create_router(service: AnalysisService, *, read_actor):
    router = APIRouter(tags=["Capabilities"])

    @router.get("/capabilities", response_model=tuple[Capability, ...])
    def capabilities(actor: Actor = Depends(read_actor)):
        return service.capabilities(actor)

    return router
