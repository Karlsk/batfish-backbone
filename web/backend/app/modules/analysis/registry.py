from pydantic import ValidationError

from app.contracts.base import thaw
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.modules.analysis.schemas import Capability, Entry
from app.modules.analysis.schemas.bgp import BgpRequest
from app.modules.analysis.schemas.filters import (
    FilterLineReachabilityRequest,
    FilterTestRequest,
    ResolveFiltersRequest,
    SearchFiltersRequest,
)
from app.modules.analysis.schemas.inventory import InterfacesRequest, NodesRequest
from app.modules.analysis.schemas.routing import LpmRequest, RoutesRequest
from app.modules.analysis.schemas.topology import TopologyRequest
from app.modules.analysis.schemas.traceroute import TraceRequest


class Registry:
    def __init__(self, entries=None):
        defaults = [
            Entry(
                "test-filters",
                "Local ACL flow test",
                stage=2,
                request_model=FilterTestRequest,
                enabled=True,
                question_id="testFilters",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "resolve-filters",
                "Available ACL filters",
                stage=2,
                request_model=ResolveFiltersRequest,
                enabled=True,
                question_id="resolveFilterSpecifier",
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "search-filters",
                "ACL matching flow search",
                stage=2,
                request_model=SearchFiltersRequest,
                enabled=True,
                question_id="searchFilters",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "filter-line-reachability",
                "ACL unreachable rules",
                stage=2,
                request_model=FilterLineReachabilityRequest,
                enabled=True,
                question_id="filterLineReachability",
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "bgp-sessions",
                "BGP model sessions",
                stage=2,
                request_model=BgpRequest,
                enabled=True,
                question_id="bgp-sessions",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "topology",
                "Topology relations",
                stage=2,
                request_model=TopologyRequest,
                enabled=True,
                question_id="topology",
                result_kind="graph",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "nodes",
                "Devices",
                request_model=NodesRequest,
                enabled=True,
                question_id="nodeProperties",
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "interfaces",
                "Interfaces",
                request_model=InterfacesRequest,
                enabled=True,
                question_id="interfaceProperties",
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "routes",
                "Routes",
                request_model=RoutesRequest,
                enabled=True,
                question_id="routes",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "lpm-routes",
                "Longest prefix match",
                request_model=LpmRequest,
                enabled=True,
                question_id="lpmRoutes",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
            Entry(
                "traceroute",
                "Virtual traceroute",
                request_model=TraceRequest,
                enabled=True,
                question_id="traceroute",
                result_kind="traces",
                requires_dataplane=True,
                to_sdk=lambda request: request.model_dump(mode="json"),
            ),
        ]
        self._entries = {entry.id: entry for entry in (defaults if entries is None else entries)}

    def get(self, identifier):
        entry = self._entries.get(identifier)
        if entry is None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=(
                    FieldError(
                        path=("body", "question_id"), message="Unknown registered capability"
                    ),
                ),
            )
        return entry

    def capabilities(self):
        results = []
        for entry in self._entries.values():
            schema = entry.request_model.model_json_schema()
            options_field = entry.request_model.model_fields["options"]
            options_schema = options_field.annotation.model_json_schema()
            defaults = {
                key: value["default"]
                for key, value in schema.get("properties", {}).items()
                if "default" in value
            }
            if options_field.default_factory is not None:
                defaults["options"] = options_field.default_factory().model_dump(mode="json")

            results.append(
                Capability(
                    id=entry.id,
                    label=entry.label,
                    stage=entry.stage,
                    enabled=entry.enabled,
                    disabled_reason=entry.disabled_reason if not entry.enabled else None,
                    required_fields=tuple(schema.get("required", [])),
                    parameters_schema=schema,
                    options_schema=options_schema,
                    defaults=defaults,
                    result_kind=entry.result_kind,
                    requires_dataplane=entry.requires_dataplane,
                    schema_version=entry.schema_version,
                )
            )
        return tuple(results)

    def validate(self, identifier, request, *, require_enabled=True, path_prefix=("body",)):
        entry = self.get(identifier)
        try:
            model = entry.request_model.model_validate(thaw(request))
        except ValidationError as error:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=tuple(
                    FieldError(path=(*path_prefix, *item["loc"]), message="Invalid value")
                    for item in error.errors()
                ),
            ) from None
        if require_enabled and not entry.enabled:
            raise ServiceError(
                ErrorCode.CONFLICT,
                field_errors=(
                    FieldError(path=("body", "question_id"), message="Capability is disabled"),
                ),
            )
        return model
