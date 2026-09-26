"""Durable comparison-bound configuration diff jobs without SDK calls."""

from dataclasses import dataclass
from uuid import UUID

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.modules.auth.service import AuthService
from app.modules.changes.config_diff import (
    MAX_DETAIL_FILES,
    MAX_FILE_BYTES,
    MAX_FILE_LINES,
    MAX_TOTAL_DETAIL_BYTES,
    file_difference,
    needs_lines,
)
from app.modules.changes.schemas import ConfigDiffRequest
from app.modules.changes.service import ChangesService
from app.modules.jobs.service import JobsService
from app.modules.results.service import ResultsService
from app.modules.snapshots.service import SnapshotsService

SCHEMA_VERSION = "config-diff-v1"


@dataclass(frozen=True)
class PreparedConfigDiff:
    context: object
    parameters: dict
    cache_key: str
    coverage: str
    coverage_notes: tuple[str, ...]
    files: tuple
    cached_result_id: UUID | None = None


class ConfigDiffService:
    def __init__(
        self,
        auth: AuthService,
        changes: ChangesService,
        snapshots: SnapshotsService,
        jobs: JobsService,
        results: ResultsService,
    ):
        self._auth, self._changes = auth, changes
        self._snapshots, self._jobs, self._results = snapshots, jobs, results

    def submit(
        self,
        actor,
        comparison_id: UUID,
        request: ConfigDiffRequest,
        *,
        idempotency_key=None,
        retry_of=None,
    ):
        actor = self._auth.revalidate_actor(actor)
        with self._jobs.resource_boundary() as tx:
            context = self._changes.context(actor, comparison_id, transaction=tx).model_copy(
                update={"schema_version": SCHEMA_VERSION}
            )
            parameters = {
                "operation": "config-diff",
                "comparison_id": str(comparison_id),
                "request": request.model_dump(mode="json"),
            }
            return self._jobs.submit(
                actor,
                "analysis",
                context,
                parameters,
                idempotency_key,
                effective_parameters=parameters,
                retry_of=retry_of,
                transaction=tx,
            )

    def _lines(self, actor, network_id, snapshot_id, entry):
        if entry is None or not needs_lines(entry):
            return None, ()
        lines, warnings = [], set()
        offset = 0
        while True:
            page = self._snapshots.read_file(
                actor, network_id, snapshot_id, entry.id, offset=offset, limit=200
            )
            lines.extend(page.lines)
            warnings.update(page.warnings)
            offset += len(page.lines)
            if offset >= (page.total or 0) or not page.lines:
                break
        return tuple(lines), tuple(sorted(warnings))

    def execute(self, job):
        actor = self._auth.revalidate_actor(
            Actor(user_id=job.created_by, role="member", enabled=True)
        )
        if job.requested_parameters.get("operation") != "config-diff":
            raise ServiceError(ErrorCode.CONFLICT)
        comparison_id = UUID(job.requested_parameters["comparison_id"])
        with self._jobs.resource_boundary() as tx:
            context = self._changes.context(actor, comparison_id, transaction=tx).model_copy(
                update={"schema_version": SCHEMA_VERSION}
            )
            comparison = self._changes.get(actor, comparison_id)
        if context.model_dump(mode="json") != job.context.model_dump(mode="json"):
            raise ServiceError(ErrorCode.CONFLICT)
        parameters = {
            "operation": "config-diff",
            "comparison_id": str(comparison_id),
            "request": ConfigDiffRequest.model_validate(
                job.effective_parameters["request"]
            ).model_dump(mode="json"),
        }
        key = self._results.cache_key(
            context,
            comparison.candidate_content_hash,
            "config-diff",
            SCHEMA_VERSION,
            parameters,
            reference_hash=comparison.baseline_content_hash,
            output_limits={
                **self._results.output_limits,
                "detail_lines": MAX_FILE_LINES,
                "detail_bytes": MAX_FILE_BYTES,
                "total_detail_bytes": MAX_TOTAL_DETAIL_BYTES,
                "detail_files": MAX_DETAIL_FILES,
            },
        )
        self._jobs.set_phase(job.id, job.lease_owner, "checking_cache")
        cached = self._results.cached(key)
        if cached:
            return PreparedConfigDiff(
                context, parameters, key, comparison.coverage, comparison.coverage_notes, (), cached
            )
        self._jobs.set_phase(job.id, job.lease_owner, "querying")
        network_id = context.network_id
        baseline = {
            item.path: item
            for item in self._snapshots.files(
                actor, network_id, context.reference_snapshot_id
            ).items
        }
        candidate = {
            item.path: item
            for item in self._snapshots.files(actor, network_id, context.snapshot_id).items
        }
        files = []
        detail_files, detail_bytes = 0, 0
        for path in sorted(baseline.keys() | candidate.keys()):
            left, right = baseline.get(path), candidate.get(path)
            if left is not None and right is not None and left.sha256 == right.sha256:
                continue
            eligible = all(entry is None or needs_lines(entry) for entry in (left, right))
            expected_bytes = sum(entry.size_bytes for entry in (left, right) if entry)
            detail_allowed = not eligible or (
                detail_files < MAX_DETAIL_FILES
                and detail_bytes + expected_bytes <= MAX_TOTAL_DETAIL_BYTES
            )
            if eligible and detail_allowed:
                detail_files += 1
                detail_bytes += expected_bytes
            read_allowed = eligible and detail_allowed
            left_lines, left_warnings = (
                self._lines(actor, network_id, context.reference_snapshot_id, left)
                if read_allowed
                else (None, ())
            )
            right_lines, right_warnings = (
                self._lines(actor, network_id, context.snapshot_id, right)
                if read_allowed
                else (None, ())
            )
            summary, hunks = file_difference(
                left, right, left_lines, right_lines, detail_allowed=detail_allowed
            )
            warnings = tuple(dict.fromkeys((*summary["warnings"], *left_warnings, *right_warnings)))
            summary["warnings"] = list(warnings)
            if "DECODING_REPLACEMENT" in warnings:
                summary["detail_truncated"] = True
            files.append((summary, hunks))
        return PreparedConfigDiff(
            context,
            parameters,
            key,
            comparison.coverage,
            comparison.coverage_notes,
            tuple(files),
        )

    def publish(self, job, value: PreparedConfigDiff, *, transaction):
        if value.cached_result_id is not None:
            return value.cached_result_id
        return self._results.publish_diff(
            value.context,
            value.files,
            parameters=value.parameters,
            cache_key=value.cache_key,
            coverage=value.coverage,
            coverage_notes=value.coverage_notes,
            transaction=transaction,
        ).id

    def retry(self, actor, job, *, idempotency_key=None):
        if job.context is None or job.requested_parameters.get("operation") != "config-diff":
            raise ServiceError(ErrorCode.CONFLICT)
        request = ConfigDiffRequest.model_validate(job.requested_parameters["request"])
        return self.submit(
            actor,
            UUID(job.requested_parameters["comparison_id"]),
            request,
            idempotency_key=idempotency_key,
            retry_of=job.id,
        )
