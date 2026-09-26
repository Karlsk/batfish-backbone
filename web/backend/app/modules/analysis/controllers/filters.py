from pybatfish.datamodel import HeaderConstraints

from app.modules.analysis.controllers.inventory import selector


def test_filters(session, parameters):
    options = parameters["options"]
    headers = HeaderConstraints(
        srcIps=parameters["source_ip"],
        dstIps=parameters["destination_ip"],
        ipProtocols=["ahp" if item == "ah" else item for item in options["ip_protocols"]],
        srcPorts=",".join(str(item) for item in options["source_ports"])
        if options["source_ports"]
        else None,
        dstPorts=",".join(str(item) for item in options["destination_ports"])
        if options["destination_ports"]
        else None,
    )
    kwargs = {"filters": selector(parameters["filters"]), "headers": headers}
    if parameters["nodes"] is not None:
        kwargs["nodes"] = selector(parameters["nodes"])
    return session.q.testFilters(**kwargs)


def resolve_filters(session, parameters):
    kwargs = {"filters": parameters["filter_expression"] or "/.*/"}
    if parameters["nodes"] is not None:
        kwargs["nodes"] = selector(parameters["nodes"])
    return session.q.resolveFilterSpecifier(**kwargs)


def normalize_filter_rows(rows):
    normalized = []
    for row in rows:
        references = []
        for tree in row.get("Trace") or []:
            for fragment in tree.get("traceElement", {}).get("fragments", []):
                source = fragment.get("vendorStructureId")
                if not isinstance(source, dict):
                    continue
                reference = {
                    key: source[key]
                    for key in ("filename", "structureName", "structureType")
                    if isinstance(source.get(key), str)
                }
                if reference and reference not in references:
                    references.append(reference)
        normalized.append(
            row
            | {
                "Implicit_Deny": row.get("Action") == "DENY"
                and row.get("Line_Content") == "no-match"
                and not row.get("Trace"),
                "Source_References": references,
            }
        )
    return normalized


QUERIES = {"testFilters": test_filters, "resolveFilterSpecifier": resolve_filters}
