from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.contracts.dto import Actor, JobDTO
from app.contracts.routing import RoutesRequest
from app.modules.analysis.schemas import Capability
from app.modules.analysis.schemas.bgp import BgpRequest
from app.modules.analysis.schemas.expert import ExpertQueryRequest
from app.modules.analysis.schemas.filters import (
    FilterLineReachabilityRequest,
    FilterTestRequest,
    ResolveFiltersRequest,
    SearchFiltersRequest,
)
from app.modules.analysis.schemas.inventory import InterfacesRequest, NodesRequest
from app.modules.analysis.schemas.routing import LpmRequest
from app.modules.analysis.schemas.topology import TopologyRequest
from app.modules.analysis.schemas.traceroute import TraceRequest
from app.modules.analysis.service import AnalysisService


def create_router(service: AnalysisService, *, read_actor, write_actor):
    router = APIRouter(tags=["Capabilities"])

    @router.get("/capabilities", response_model=tuple[Capability, ...])
    def capabilities(actor: Actor = Depends(read_actor)):
        return service.capabilities(actor)

    base = "/networks/{network_id}/snapshots/{snapshot_id}/analyses"

    @router.post(base + "/query", response_model=JobDTO, status_code=202)
    def query(
        network_id: UUID,
        snapshot_id: UUID,
        body: ExpertQueryRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit_query(
            actor,
            network_id,
            snapshot_id,
            body.question_id,
            body.parameters,
            idempotency_key=idempotency_key,
        )

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

    @router.post(base + "/test-filters", response_model=JobDTO, status_code=202)
    def test_filters(
        network_id: UUID,
        snapshot_id: UUID,
        body: FilterTestRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "test-filters",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/resolve-filters", response_model=JobDTO, status_code=202)
    def resolve_filters(
        network_id: UUID,
        snapshot_id: UUID,
        body: ResolveFiltersRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "resolve-filters",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/search-filters", response_model=JobDTO, status_code=202)
    def search_filters(
        network_id: UUID,
        snapshot_id: UUID,
        body: SearchFiltersRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "search-filters",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    @router.post(base + "/filter-line-reachability", response_model=JobDTO, status_code=202)
    def filter_line_reachability(
        network_id: UUID,
        snapshot_id: UUID,
        body: FilterLineReachabilityRequest,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(None, max_length=128),
    ):
        return service.submit(
            actor,
            network_id,
            snapshot_id,
            "filter-line-reachability",
            body.model_dump(mode="json", exclude_unset=True),
            idempotency_key=idempotency_key,
        )

    return router
