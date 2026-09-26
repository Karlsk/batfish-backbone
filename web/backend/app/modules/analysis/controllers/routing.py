from app.contracts.errors import ErrorCode, ServiceError
from app.modules.analysis.controllers.inventory import selector

ROUTE_DIFF_CHANGES = {
    "Only in Snapshot": "added",
    "Only in Reference": "removed",
    "Changed": "changed",
}


def normalize_route_diff_rows(rows):
    """Keep every SDK route row, including multiple next hops for one prefix."""
    normalized = []
    for row in rows:
        marker = row.get("Entry_Presence")
        if marker == "Unchanged":
            continue
        if marker not in ROUTE_DIFF_CHANGES:
            raise ServiceError(ErrorCode.ENGINE_QUERY_FAILED)
        normalized.append({**row, "Change": ROUTE_DIFF_CHANGES[marker]})
    return normalized


def vrf_regex(value):
    if value["mode"] == "expression":
        return value["expression"]
    return selector(value)[1:-1]


def common(parameters):
    options = parameters["options"]
    kwargs = {}
    if parameters["nodes"] is not None:
        kwargs["nodes"] = selector(parameters["nodes"])
    if options["vrfs"] is not None:
        kwargs["vrfs"] = vrf_regex(options["vrfs"])
    return kwargs


def routes(session, parameters):
    options = parameters["options"]
    kwargs = common(parameters)
    kwargs.update(rib=options["rib"], prefixMatchType=options["prefix_match_type"])
    if options["network"] is not None:
        kwargs["network"] = options["network"]
    if options["protocols"] is not None:
        kwargs["protocols"] = ",".join(options["protocols"])
    return session.q.routes(**kwargs)


def lpm(session, parameters):
    return session.q.lpmRoutes(ip=parameters["ip"], **common(parameters))


QUERIES = {"routes": routes, "lpmRoutes": lpm}
