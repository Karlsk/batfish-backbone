import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.base import thaw
from app.contracts.dto import ResultEnvelope
from app.contracts.errors import ErrorCode, ServiceError
from app.contracts.results import FlowPage, TablePage, TraceFlow, TracePage
from app.infrastructure.storage import FileStore
from app.modules.auth.service import AuthService
from app.modules.results.export import download
from app.modules.results.repository import ResultsRepository


def encoded(value):
    return json.dumps(
        thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def cell_order(value):
    if value is None:
        return (4, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (1, value)
    if isinstance(value, str):
        return (2, value)
    return (3, encoded(value))


class ResultsService:
    def __init__(self, database, auth: AuthService, settings):
        self._database, self._auth, self._settings = database, auth, settings
        self._root = settings.data_dir / "results"

    @staticmethod
    def cache_key(
        context,
        content_hash,
        operation,
        question_version,
        parameters,
        *,
        reference_hash=None,
        output_limits=None,
    ):
        return hashlib.sha256(
            encoded(
                {
                    "context": context.model_dump(mode="json"),
                    "content_hash": content_hash,
                    "reference_hash": reference_hash,
                    "output_limits": output_limits,
                    "operation": operation,
                    "question_version": question_version,
                    "parameters": parameters,
                }
            )
        ).hexdigest()

    @property
    def output_limits(self):
        return {"bytes": self._settings.result_max_bytes, "rows": self._settings.table_rows}

    def cached(self, key):
        with self._database.transaction() as tx:
            return ResultsRepository(tx).cached(key)

    def publish(self, context, answer, *, parameters, quality, cache_key, transaction):
        payload = {
            "columns": [column.model_dump(mode="json") for column in answer.columns],
            "rows": [],
            "flows": [],
        }
        size = len(encoded(payload))
        if size > self._settings.result_max_bytes:
            raise ServiceError(ErrorCode.NOT_READY)
        truncated, reasons = False, []
        entries = payload["rows"] if answer.kind == "table" else payload["flows"]
        for index, frozen in enumerate(answer.rows):
            if index >= self._settings.table_rows:
                truncated = True
                reasons.append("row_limit")
                break
            row = thaw(frozen)
            if answer.kind == "traces":
                traces = row.get("Traces", [])
                flow = row.get("Flow", {})
                count = int(row.get("TraceCount", len(traces)))
                if count < len(traces):
                    raise ValueError("Invalid trace count")
                row = {
                    "flow_id": str(index),
                    "headers": flow,
                    "start_location": flow.get("ingressNode"),
                    "trace_count": count,
                    "returned_trace_count": len(traces),
                    "truncated": count > len(traces),
                    "traces": traces,
                    "dispositions": dict(
                        Counter(str(trace.get("disposition", "UNKNOWN")) for trace in traces)
                    ),
                }
                if row["truncated"]:
                    truncated = True
                    reasons.append("trace_limit")
            increment = len(encoded(row)) + (1 if entries else 0)
            if size + increment > self._settings.result_max_bytes:
                truncated = True
                reasons.append("byte_limit")
                break
            entries.append(row)
            size += increment
        raw = encoded(payload)
        assert len(raw) <= self._settings.result_max_bytes
        identifier = uuid4()
        model_warnings = tuple(str(item["description"]) for item in quality.get("model_limits", ()))
        summary = {
            "returned_rows": len(entries),
            "total_rows": len(answer.rows),
            "quality": quality,
        }
        warnings = [*answer.warnings, *model_warnings]
        if answer.kind == "traces":
            dispositions = Counter()
            for flow in entries:
                dispositions.update(flow["dispositions"])
            summary.update(
                dispositions=dict(dispositions),
                disposition_scope="returned_traces",
                trace_count_scope="stored_flows",
                trace_count=sum(flow["trace_count"] for flow in entries),
                returned_trace_count=sum(flow["returned_trace_count"] for flow in entries),
            )
            if parameters.get("operation") == "traceroute":
                ignore_filters = bool(parameters["request"]["options"]["ignore_filters"])
                summary["ignore_filters"] = ignore_filters
                warnings.append(
                    "Single-direction model analysis; not a live probe or reverse-path proof"
                )
                if ignore_filters:
                    warnings.append("ACL filters were ignored")
        envelope = ResultEnvelope(
            id=identifier,
            kind=answer.kind,
            schema_version=context.schema_version,
            context=context,
            effective_parameters=parameters,
            summary=summary,
            warnings=tuple(dict.fromkeys(warnings)),
            coverage=quality.get("coverage", "unknown"),
            truncated=truncated,
            truncation_reason=",".join(sorted(set(reasons))) if truncated else None,
            created_at=datetime.now(UTC),
        )
        with FileStore(self._root) as store, store.stage(str(identifier), raw) as pending:
            ResultsRepository(transaction).add(
                envelope, storage_key=pending.key, cache_key=cache_key
            )
            pending.publish()
            # A failed/unknown DB commit leaves an unreferenced immutable file, never a visible result.
        return envelope

    def get(self, actor, result_id):
        self._auth.revalidate_actor(actor)
        with self._database.transaction() as tx:
            result = ResultsRepository(tx).get(result_id)
        if result is None:
            raise ServiceError(ErrorCode.NOT_FOUND)
        return result

    def _payload(self, actor, result_id, kind):
        result = self.get(actor, result_id)
        if result.kind != kind:
            raise ServiceError(ErrorCode.CONFLICT)
        with self._database.transaction() as tx:
            key = ResultsRepository(tx).storage_key(result_id)
        with FileStore(self._root) as store:
            payload = json.loads(store.read(key))
        return result, payload

    def export(self, actor, result_id, *, format="json"):
        if format not in {"json", "csv"}:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        result = self.get(actor, result_id)
        if format == "csv" and result.kind != "table":
            raise ServiceError(ErrorCode.CONFLICT)
        result, payload = self._payload(actor, result_id, result.kind)
        return download(result, payload, format)

    @staticmethod
    def _page(offset, limit):
        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)

    def rows(self, actor, result_id, *, offset=0, limit=50, sort=None, filters=()):
        self._page(offset, limit)
        result, payload = self._payload(actor, result_id, "table")
        columns = {column["key"] for column in payload["columns"]}
        rows = payload["rows"]
        if sort is not None and sort.removeprefix("-") not in columns:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        for item in filters:
            if item.column not in columns or item.op not in {"eq", "contains"}:
                raise ServiceError(ErrorCode.VALIDATION_ERROR)
            expected = thaw(item.value)
            rows = [
                row
                for row in rows
                if (
                    row.get(item.column) == expected
                    if item.op == "eq"
                    else isinstance(row.get(item.column), str)
                    and isinstance(expected, str)
                    and expected in row[item.column]
                )
            ]
        if sort:
            key = sort.removeprefix("-")
            # Stable typed ordering; nested cells use canonical JSON and never compare unlike values.
            rows = sorted(
                rows, key=lambda row: cell_order(row.get(key)), reverse=sort.startswith("-")
            )
        return TablePage(
            columns=payload["columns"],
            rows=rows[offset : offset + limit],
            offset=offset,
            limit=limit,
            total=len(rows),
            truncated=result.truncated,
        )

    def flows(self, actor, result_id, *, offset=0, limit=50):
        self._page(offset, limit)
        result, payload = self._payload(actor, result_id, "traces")
        flows = payload["flows"]
        return FlowPage(
            items=[
                TraceFlow(**{key: value for key, value in flow.items() if key != "traces"})
                for flow in flows[offset : offset + limit]
            ],
            offset=offset,
            limit=limit,
            total=len(flows),
            truncated=result.truncated,
        )

    def traces(self, actor, result_id, flow_id, *, offset=0, limit=50):
        self._page(offset, limit)
        result, payload = self._payload(actor, result_id, "traces")
        flow = next((flow for flow in payload["flows"] if flow["flow_id"] == flow_id), None)
        if flow is None:
            raise ServiceError(ErrorCode.NOT_FOUND)
        return TracePage(
            items=flow["traces"][offset : offset + limit],
            offset=offset,
            limit=limit,
            total=len(flow["traces"]),
            trace_count=flow["trace_count"],
            truncated=flow["truncated"] or result.truncated,
        )
