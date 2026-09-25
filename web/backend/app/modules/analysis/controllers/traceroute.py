from pybatfish.datamodel import HeaderConstraints


def traceroute(session, parameters):
    options = parameters["options"]
    headers = HeaderConstraints(
        dstIps=parameters["destination_ip"],
        srcIps=options["source_ip"],
        ipProtocols=["ahp" if p == "ah" else p for p in options["ip_protocols"]],
        srcPorts=",".join(str(p) for p in options["source_ports"])
        if options["source_ports"]
        else None,
        dstPorts=",".join(str(p) for p in options["destination_ports"])
        if options["destination_ports"]
        else None,
    )
    return session.q.traceroute(
        startLocation=parameters["start_location"],
        headers=headers,
        maxTraces=options["max_traces"],
        ignoreFilters=options["ignore_filters"],
    )


QUERIES = {"traceroute": traceroute}
