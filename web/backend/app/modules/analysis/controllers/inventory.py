def selector(value):
    if value is None:
        return None
    if value["mode"] == "expression":
        return value["expression"]
    # The engine uses Java regexes. Encode every code point so no user character
    # becomes a regex or specifier operator, even quotes, slashes and backslashes.
    terms = ["".join("\\x{" + format(ord(c), "x") + "}" for c in name) for name in value["values"]]
    return "/^(?:" + "|".join(terms) + ")$/"


def nodes(session, parameters):
    options = parameters["options"]
    kwargs = {"properties": ",".join(options["properties"])}
    if options["nodes"] is not None:
        kwargs["nodes"] = selector(options["nodes"])
    return session.q.nodeProperties(**kwargs)


def interfaces(session, parameters):
    options = parameters["options"]
    kwargs = {"properties": ",".join(options["properties"])}
    if parameters["nodes"] is not None:
        kwargs["nodes"] = selector(parameters["nodes"])
    if options["interfaces"] is not None:
        kwargs["interfaces"] = selector(options["interfaces"])
    return session.q.interfaceProperties(**kwargs)


QUERIES = {"nodeProperties": nodes, "interfaceProperties": interfaces}
