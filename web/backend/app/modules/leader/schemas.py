from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime

from app.contracts.base import Contract


class SnapshotSource(Contract):
    id: UUID
    display_name: str
    status: str
    created_at: AwareDatetime
    node_count: int | None = None
    issue_count: int | None = None
    coverage: str | None = None
    model_limit_count: int = 0


class JobSource(Contract):
    id: UUID
    snapshot_id: UUID
    status: str
    phase: str
    result_id: UUID | None
    created_at: AwareDatetime
    finished_at: AwareDatetime | None


class ResultSource(Contract):
    id: UUID
    snapshot_id: UUID
    coverage: Literal["complete", "limited", "unknown"]
    truncated: bool
    truncation_reason: str | None
    warning_count: int
    created_at: AwareDatetime


class NetworkOverview(Contract):
    network_id: UUID
    display_name: str
    sync_state: str
    readiness: Literal["pending", "ready", "warning"]
    check_state: Literal[
        "not_checked",
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
        "result_unavailable",
        "result_available",
    ]
    concern_count: int
    latest_snapshot: SnapshotSource | None
    latest_ready_snapshot: SnapshotSource | None
    latest_job: JobSource | None
    latest_result: ResultSource | None


class OverviewCounts(Contract):
    network_states: dict[str, int]
    snapshot_states: dict[str, int]
    analysis_job_states: dict[str, int]


class RecentComparison(Contract):
    id: UUID
    network_id: UUID
    network_display_name: str
    display_name: str
    baseline_snapshot_id: UUID
    candidate_snapshot_id: UUID
    coverage: Literal["complete", "limited"]
    created_at: AwareDatetime


class OverviewPage(Contract):
    items: tuple[NetworkOverview, ...]
    offset: int
    limit: int
    total: int
    counts: OverviewCounts
    recent_comparisons: tuple[RecentComparison, ...]
