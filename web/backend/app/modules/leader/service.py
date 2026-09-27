from uuid import UUID

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.modules.auth.service import AuthService
from app.modules.business_concerns.service import BusinessConcernsService
from app.modules.changes.service import ChangesService
from app.modules.jobs.service import JobsService
from app.modules.leader.schemas import (
    JobSource,
    NetworkOverview,
    OverviewCounts,
    OverviewPage,
    RecentComparison,
    ResultSource,
    SnapshotSource,
)
from app.modules.networks.service import NetworksService
from app.modules.results.service import ResultsService
from app.modules.snapshots.service import SnapshotsService


def snapshot_source(snapshot):
    if snapshot is None:
        return None
    quality = snapshot.quality_summary
    limits = quality.get("model_limits")
    return SnapshotSource(
        id=snapshot.id,
        display_name=snapshot.display_name,
        status=snapshot.status,
        created_at=snapshot.created_at,
        node_count=quality.get("node_count")
        if isinstance(quality.get("node_count"), int)
        else None,
        issue_count=quality.get("issue_count")
        if isinstance(quality.get("issue_count"), int)
        else None,
        coverage=quality.get("coverage") if isinstance(quality.get("coverage"), str) else None,
        model_limit_count=len(limits) if isinstance(limits, (tuple, list)) else 0,
    )


class LeaderService:
    def __init__(
        self,
        auth: AuthService,
        networks: NetworksService,
        snapshots: SnapshotsService,
        jobs: JobsService,
        results: ResultsService,
        concerns: BusinessConcernsService,
        changes: ChangesService,
    ):
        self._auth = auth
        self._networks = networks
        self._snapshots = snapshots
        self._jobs = jobs
        self._results = results
        self._concerns = concerns
        self._changes = changes

    def _cards(self, actor: Actor, networks) -> tuple[NetworkOverview, ...]:
        network_ids = tuple(item.id for item in networks)
        latest, ready = self._snapshots.latest_for_networks(actor, network_ids)
        ready_ids = tuple(snapshot.id for snapshot in ready.values())
        jobs = self._jobs.latest_analysis_for_snapshots(actor, ready_ids)
        results = self._results.latest_for_snapshots(actor, ready_ids)
        concern_counts = self._concerns.active_counts(actor, network_ids)
        cards = []
        for network in networks:
            newest = latest.get(network.id)
            baseline = ready.get(network.id)
            job = jobs.get(baseline.id) if baseline else None
            result = results.get(baseline.id) if baseline else None
            if not baseline:
                readiness = "pending"
            elif (
                baseline.status == "ready_with_warnings"
                or newest.id != baseline.id
                or network.sync_state != "ready"
            ):
                readiness = "warning"
            else:
                readiness = "ready"
            if job is None:
                check_state = "result_available" if result else "not_checked"
            elif job.status == "succeeded" and (
                not job.result_id or result is None or result.id != job.result_id
            ):
                check_state = "result_unavailable"
            else:
                check_state = job.status
            cards.append(
                NetworkOverview(
                    network_id=network.id,
                    display_name=network.display_name,
                    sync_state=network.sync_state,
                    readiness=readiness,
                    check_state=check_state,
                    concern_count=concern_counts.get(network.id, 0),
                    latest_snapshot=snapshot_source(newest),
                    latest_ready_snapshot=snapshot_source(baseline),
                    latest_job=(
                        JobSource(
                            id=job.id,
                            snapshot_id=baseline.id,
                            status=job.status,
                            phase=job.phase,
                            result_id=job.result_id,
                            created_at=job.created_at,
                            finished_at=job.finished_at,
                        )
                        if job
                        else None
                    ),
                    latest_result=(
                        ResultSource(
                            id=result.id,
                            snapshot_id=baseline.id,
                            coverage=result.coverage,
                            truncated=result.truncated,
                            truncation_reason=result.truncation_reason,
                            warning_count=len(result.warnings),
                            created_at=result.created_at,
                        )
                        if result
                        else None
                    ),
                )
            )
        return tuple(cards)

    def network_detail(self, actor: Actor, network_id: UUID) -> NetworkOverview:
        self._auth.revalidate_actor(actor)
        network = self._networks.get(actor, network_id)
        return self._cards(actor, (network,))[0]

    def overview(self, actor: Actor, *, offset: int, limit: int) -> OverviewPage:
        self._auth.revalidate_actor(actor)
        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        page = self._networks.list(actor, offset=offset, limit=limit)
        return OverviewPage(
            items=self._cards(actor, page.items),
            offset=offset,
            limit=limit,
            total=page.total,
            counts=OverviewCounts(
                network_states=self._networks.state_counts(actor),
                snapshot_states=self._snapshots.status_counts(actor),
                analysis_job_states=self._jobs.analysis_status_counts(actor),
            ),
            recent_comparisons=tuple(
                RecentComparison(
                    id=comparison.id,
                    network_id=comparison.network_id,
                    network_display_name=network_name,
                    display_name=comparison.display_name,
                    baseline_snapshot_id=comparison.baseline_snapshot_id,
                    candidate_snapshot_id=comparison.candidate_snapshot_id,
                    coverage=comparison.coverage,
                    created_at=comparison.created_at,
                )
                for comparison, network_name in self._changes.recent(actor)
            ),
        )
