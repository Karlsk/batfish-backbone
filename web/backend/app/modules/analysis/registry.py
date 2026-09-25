from pydantic import ValidationError

from app.contracts.base import thaw
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.modules.analysis.schemas import Capability, Entry
from app.modules.analysis.schemas.inventory import InterfacesRequest, NodesRequest
from app.modules.analysis.schemas.routing import LpmRequest, RoutesRequest


class Registry:
    def __init__(self, entries=None):
        defaults = [
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
                "traceroute", "Virtual traceroute", result_kind="traces", requires_dataplane=True
            ),
        ]
        self._entries = {entry.id: entry for entry in (defaults if entries is None else entries)}

    def get(self, identifier):
        entry = self._entries.get(identifier)
        if entry is None:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
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
                    stage=1,
                    enabled=entry.enabled,
                    disabled_reason=entry.disabled_reason if not entry.enabled else None,
                    required_fields=tuple(schema.get("required", [])),
                    options_schema=options_schema,
                    defaults=defaults,
                    result_kind=entry.result_kind,
                    requires_dataplane=entry.requires_dataplane,
                    schema_version=entry.schema_version,
                )
            )
        return tuple(results)

    def validate(self, identifier, request, *, require_enabled=True):
        entry = self.get(identifier)
        try:
            model = entry.request_model.model_validate(thaw(request))
        except ValidationError as error:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=tuple(
                    FieldError(path=("body", *item["loc"]), message="Invalid value")
                    for item in error.errors()
                ),
            ) from None
        if require_enabled and not entry.enabled:
            raise ServiceError(ErrorCode.CONFLICT)
        return model
