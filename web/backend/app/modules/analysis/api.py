from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.contracts.dto import Actor, JobDTO
from app.modules.analysis.schemas import Capability
from app.modules.analysis.schemas.bgp import BgpRequest
from app.modules.analysis.schemas.inventory import InterfacesRequest, NodesRequest
from app.modules.analysis.schemas.routing import LpmRequest, RoutesRequest
from app.modules.analysis.schemas.topology import TopologyRequest
from app.modules.analysis.schemas.traceroute import TraceRequest
from app.modules.analysis.service import AnalysisService


def create_router(service: AnalysisService, *, read_actor, write_actor):
    router = APIRouter(tags=["Capabilities"])

    @router.get("/capabilities", response_model=tuple[Capability, ...])
    def capabilities(actor: Actor = Depends(read_actor)):
        return service.capabilities(actor)

    base = "/networks/{network_id}/snapshots/{snapshot_id}/analyses"

    @router.post(base + "/nodes", response_model=JobDTO, status_code=202)
    def nodes(
        network_id: UUID,
        snapshot_id: UUID,
        body: NodesRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "nodes",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/interfaces", response_model=JobDTO, status_code=202)
    def interfaces(
        network_id: UUID,
        snapshot_id: UUID,
        body: InterfacesRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "interfaces",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/routes", response_model=JobDTO, status_code=202)
    def routes(
        network_id: UUID,
        snapshot_id: UUID,
        body: RoutesRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "routes",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/lpm-routes", response_model=JobDTO, status_code=202)
    def lpm_routes(
        network_id: UUID,
        snapshot_id: UUID,
        body: LpmRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "lpm-routes",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/traceroute", response_model=JobDTO, status_code=202)
    def traceroute(
        network_id: UUID,
        snapshot_id: UUID,
        body: TraceRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "traceroute",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/topology", response_model=JobDTO, status_code=202)
    def topology(
        network_id: UUID,
        snapshot_id: UUID,
        body: TopologyRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "topology",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/bgp-sessions", response_model=JobDTO, status_code=202)
    def bgp_sessions(
        network_id: UUID,
        snapshot_id: UUID,
        body: BgpRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "bgp-sessions",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    return router
