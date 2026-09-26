from app.modules.analysis.controllers.inventory import selector

SOURCES = {
    "status": "bgpSessionStatus",
    "compatibility": "bgpSessionCompatibility",
}


def question_name(parameters):
    return SOURCES[parameters["options"]["mode"]]


def kwargs(parameters):
    options = parameters["options"]
    return {
        sdk: selector(options[key])
        for key, sdk in (("nodes", "nodes"), ("remote_nodes", "remoteNodes"))
        if options[key] is not None
    }


QUERIES = {
    "bgpSessionStatus": lambda session, parameters: session.q.bgpSessionStatus(
        **kwargs(parameters)
    ),
    "bgpSessionCompatibility": lambda session, parameters: session.q.bgpSessionCompatibility(
        **kwargs(parameters)
    ),
}
