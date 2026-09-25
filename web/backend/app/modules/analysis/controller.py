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
from app.modules.analysis.controllers.inventory import QUERIES


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
        self._queries = dict(QUERIES if queries is None else queries)

    def runtime_versions(self):
        with self._sessions.exclusive(owner="analysis-version-check") as session:
            return {
                "engine_version": session.get_component_versions()["Batfish"],
                "sdk_version": version("pybatfish"),
            }

    def run(self, context, question_id, sdk_parameters, *, kind="table"):
        query = self._queries.get(question_id)
        if query is None:
            raise ServiceError(ErrorCode.CONFLICT)
        failure = None
        with self._sessions.for_job(context) as session:
            try:
                question = query(session, sdk_parameters)
                started = time.monotonic()
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
                    status = session.get_work_status(work_id)["workstatus"]
                    if status in {
                        "TERMINATEDNORMALLY",
                        "TERMINATEDABNORMALLY",
                        "TERMINATEDBYUSER",
                        "ASSIGNMENTERROR",
                        "REQUEUEFAILURE",
                    }:
                        break
                    if time.monotonic() - started >= self._wait_budget:
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
                else:
                    raw = normalize(
                        session.get_answer(
                            question.get_name(),
                            context.engine_snapshot,
                            context.engine_reference_snapshot,
                        ).dict()
                    )
        if failure is not None:
            raise failure
        element = raw["answerElements"][0]
        return StructuredAnswer(
            kind=kind,
            columns=tuple(
                Column(
                    key=item["name"],
                    label=item.get("description") or item["name"],
                    type=str(item["schema"]),
                )
                for item in element["metadata"]["columnMetadata"]
            ),
            rows=tuple(element.get("rows", [])),
            warnings=("No matching rows",) if not element.get("rows") else (),
        )
