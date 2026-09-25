import json
import math
from collections.abc import Mapping
from enum import Enum
from importlib.metadata import version

from pybatfish.datamodel.primitives import DataModelElement

from app.contracts.errors import ErrorCode, ServiceError
from app.contracts.results import Column, StructuredAnswer
from app.infrastructure.sdk import SessionFactory


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
        self._queries = dict(queries or {})

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
        with self._sessions.for_job(context) as session:
            answer = query(session, sdk_parameters).answer(
                snapshot=context.engine_snapshot,
                **(
                    {"reference_snapshot": context.engine_reference_snapshot}
                    if context.engine_reference_snapshot
                    else {}
                ),
            )
            raw = normalize(answer.dict())
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
        )
