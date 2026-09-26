import json
import math
import time
from collections.abc import Mapping
from enum import Enum
from importlib.metadata import version
from urllib.parse import unquote, urlsplit

from pybatfish.datamodel.primitives import DataModelElement
from pybatfish.exception import QuestionValidationException
from requests.exceptions import HTTPError

from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.contracts.results import Column, StructuredAnswer
from app.infrastructure.sdk import SessionFactory
from app.modules.analysis.controllers.bgp import QUERIES as BGP_QUERIES
from app.modules.analysis.controllers.bgp import question_name as bgp_question_name
from app.modules.analysis.controllers.filters import QUERIES as FILTER_QUERIES
from app.modules.analysis.controllers.filters import normalize_filter_rows
from app.modules.analysis.controllers.inventory import QUERIES as INVENTORY_QUERIES
from app.modules.analysis.controllers.reachability import QUERIES as REACHABILITY_QUERIES
from app.modules.analysis.controllers.reachability import normalize_reachability_rows
from app.modules.analysis.controllers.routing import QUERIES as ROUTING_QUERIES
from app.modules.analysis.controllers.routing import normalize_route_diff_rows
from app.modules.analysis.controllers.topology import QUERIES as TOPOLOGY_QUERIES
from app.modules.analysis.controllers.topology import normalize_graph, query_plan
from app.modules.analysis.controllers.traceroute import QUERIES as TRACE_QUERIES


def normalize(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Enum):
        return normalize(value.value)
    if isinstance(value, DataModelElement):
        return normalize(value.dict())
    if isinstance(value, Mapping):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (normalize(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True)
        )
    raise TypeError("Unsupported SDK value")


class AnalysisController:
    def __init__(self, database, settings, *, queries=None):
        self._sessions = SessionFactory(database, settings)
        self._wait_budget = settings.job_wait_budget_seconds
        self._queries = dict(
            (
                INVENTORY_QUERIES
                | ROUTING_QUERIES
                | TRACE_QUERIES
                | TOPOLOGY_QUERIES
                | BGP_QUERIES
                | FILTER_QUERIES
                | REACHABILITY_QUERIES
            )
            if queries is None
            else queries
        )

    def runtime_versions(self):
        with self._sessions.exclusive(owner="analysis-version-check") as session:
            return {
                "engine_version": session.get_component_versions()["Batfish"],
                "sdk_version": version("pybatfish"),
            }

    def run(self, context, question_id, sdk_parameters, *, kind="table"):
        if question_id == "topology":
            plan = query_plan(sdk_parameters)
        elif question_id == "bgp-sessions":
            plan = [(bgp_question_name(sdk_parameters), sdk_parameters)]
        else:
            plan = [(question_id, sdk_parameters)]
        answers, failure = [], None
        deadline = time.monotonic() + self._wait_budget
        with self._sessions.for_job(context) as session:
            for question, parameters in plan:
                if answers and time.monotonic() >= deadline:
                    raise TimeoutError("Analysis wait budget exhausted")
                raw, failure = self._answer(session, context, question, parameters, deadline)
                if failure is not None:
                    break
                answers.append(raw["answerElements"][0])
        # Raise definitive errors after the gate exits normally; unknown errors
        # still escape from inside the Session and retain the engine fence.
        if failure is not None:
            raise failure
        if question_id == "topology":
            return StructuredAnswer(
                kind="graph",
                graph=normalize_graph(
                    sdk_parameters["view"],
                    [row for answer in answers[:-1] for row in answer.get("rows", [])],
                    answers[-1].get("rows", []),
                ),
                warnings=(
                    "Protocol relations are not session health; missing edges do not prove physical disconnection",
                ),
            )
        element = raw["answerElements"][0]
        columns = [
            Column(
                key=item["name"],
                label=item.get("description") or item["name"],
                type=str(item["schema"]),
            )
            for item in element["metadata"]["columnMetadata"]
        ]
        rows = element.get("rows", [])
        if question_id == "routes" and context.reference_snapshot_id is not None:
            rows = normalize_route_diff_rows(rows)
            columns.append(Column(key="Change", label="Candidate change", type="String"))
        if question_id == "differentialReachability":
            rows = normalize_reachability_rows(rows)
            columns.extend(
                (
                    Column(key="Change", label="Candidate change", type="String"),
                    Column(key="Candidate_Reachable", label="Candidate reachable", type="Boolean"),
                    Column(key="Baseline_Reachable", label="Baseline reachable", type="Boolean"),
                    Column(
                        key="Evidence_Truncated", label="Trace evidence truncated", type="Boolean"
                    ),
                    Column(
                        key="Candidate_Dispositions", label="Candidate dispositions", type="Object"
                    ),
                    Column(
                        key="Baseline_Dispositions", label="Baseline dispositions", type="Object"
                    ),
                )
            )
        if question_id in {"testFilters", "searchFilters"}:
            rows = normalize_filter_rows(rows)
            columns.extend(
                (
                    Column(key="Implicit_Deny", label="Implicit deny", type="Boolean"),
                    Column(key="Source_References", label="Source references", type="List<Object>"),
                )
            )
        return StructuredAnswer(
            kind=kind,
            columns=tuple(columns),
            rows=tuple(rows),
            warnings=(
                (("No matching rows",) if not rows else ())
                + (
                    ("BGP session state is model-predicted, not live device health",)
                    if question_id == "bgp-sessions"
                    else ()
                )
                + (
                    ("Local ACL model evaluation, not end-to-end reachability",)
                    if question_id == "testFilters"
                    else ()
                )
                + (
                    ("No filters matched; no allow/deny conclusion",)
                    if question_id == "testFilters" and not rows
                    else ()
                )
                + (
                    (
                        "No witness for this ACL, action, and header scope; this is not a network-wide safety proof",
                    )
                    if question_id == "searchFilters" and not rows
                    else ()
                )
                + (
                    (
                        "ACL search returns example flows under the selected scope, not all possible flows",
                    )
                    if question_id == "searchFilters"
                    else ()
                )
                + (
                    (
                        "No unreachable lines found in the selected ACL scope; this is not a safety proof",
                    )
                    if question_id == "filterLineReachability" and not rows
                    else ()
                )
                + (
                    ("No reachability difference witnesses in the selected scope",)
                    if question_id == "differentialReachability" and not rows
                    else ()
                )
            ),
        )

    def _answer(self, session, context, question_id, sdk_parameters, deadline):
        query = self._queries.get(question_id)
        if query is None:
            raise ServiceError(ErrorCode.CONFLICT)
        failure, raw = None, None
        try:
            question = query(session, sdk_parameters)
            work_id = question.answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
                background=True,
            )
        except QuestionValidationException:
            # SDK validation happens before submission. Exit the gate normally.
            failure = ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=(
                    FieldError(path=("request",), message="Invalid analysis parameters"),
                ),
            )
        except HTTPError as error:
            response = error.response
            # A 400 from this question's PUT is a definitive rejection before
            # work submission. Never infer this from exception text or a work POST.
            if not (
                response is not None
                and response.status_code == 400
                and response.request is not None
                and response.request.method == "PUT"
                and unquote(urlsplit(response.url).path).endswith(
                    f"/networks/{session.network}/questions/{question.get_name()}"
                )
            ):
                raise
            failure = ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=(
                    FieldError(
                        path=("request",),
                        message="Engine rejected analysis parameters; check selector syntax",
                    ),
                ),
            )
        else:
            while True:
                observation = session.get_work_status(work_id)
                status = observation["workstatus"]
                if status in {
                    "TERMINATEDNORMALLY",
                    "TERMINATEDABNORMALLY",
                    "TERMINATEDBYUSER",
                    "ASSIGNMENTERROR",
                    "REQUEUEFAILURE",
                }:
                    break
                if time.monotonic() >= deadline:
                    # A timeout is not proof that the engine stopped.
                    raise TimeoutError("Analysis outcome is unknown")
                time.sleep(0.1)
            if status != "TERMINATEDNORMALLY":
                failure = ServiceError(
                    ErrorCode.ENGINE_QUERY_FAILED,
                    field_errors=(
                        FieldError(
                            path=("request",),
                            message="Engine query ended unsuccessfully; check selectors and snapshot diagnostics",
                        ),
                    ),
                )
                if question_id == "traceroute":
                    # The status already proves termination. Diagnostic text only
                    # selects a safe user hint and never controls engine release.
                    try:
                        task = json.loads(observation.get("taskstatus") or "{}")
                        reason = str(task.get("errMessage") or "")
                    except (TypeError, ValueError, AttributeError):
                        reason = ""
                    try:
                        diagnostic = session.get_answer(
                            question.get_name(),
                            context.engine_snapshot,
                            context.engine_reference_snapshot,
                        ).dict()
                        for element in diagnostic.get("answerElements", []):
                            if element.get("class", "").endswith("BatfishStackTrace"):
                                lines = element.get("answer", [])
                                reason += "\n".join(
                                    line for line in lines[:64] if isinstance(line, str)
                                )[:65536]
                    except Exception:
                        # Best-effort read after a proven terminal status. Failure
                        # to read diagnostics cannot make that engine work run again.
                        pass
                    if "source IP" in reason or "Could not construct a flow" in reason:
                        failure = ServiceError(
                            ErrorCode.VALIDATION_ERROR,
                            field_errors=(
                                FieldError(
                                    path=("options", "source_ip"),
                                    message="Cannot infer a source IPv4 address; supply source_ip for the selected start_location",
                                ),
                            ),
                        )
                    elif "Found no active locations" in reason:
                        failure = ServiceError(
                            ErrorCode.VALIDATION_ERROR,
                            field_errors=(
                                FieldError(
                                    path=("start_location",),
                                    message="No active start location matches this selector",
                                ),
                            ),
                        )
            else:
                raw = normalize(
                    session.get_answer(
                        question.get_name(),
                        context.engine_snapshot,
                        context.engine_reference_snapshot,
                    ).dict()
                )
        return raw, failure
