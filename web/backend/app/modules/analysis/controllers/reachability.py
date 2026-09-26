"""Bounded differential reachability queries and conservative witness interpretation."""

from collections import Counter

from pybatfish.datamodel import HeaderConstraints, PathConstraints

SUCCESS = {"ACCEPTED", "DELIVERED_TO_SUBNET", "EXITS_NETWORK"}


def differential_reachability(session, parameters):
    options = parameters["options"]
    headers = HeaderConstraints(
        dstIps=parameters["destination_ips"],
        srcIps=options["source_ips"],
        ipProtocols=list(options["ip_protocols"]),
        dstPorts=",".join(map(str, options["destination_ports"]))
        if options["destination_ports"]
        else None,
    )
    return session.q.differentialReachability(
        headers=headers,
        pathConstraints=PathConstraints(startLocation=parameters["start_location"]),
        maxTraces=options["max_traces"],
    )


def _side(row, prefix):
    traces = row[f"{prefix}_Traces"]
    count = row[f"{prefix}_TraceCount"]
    if not isinstance(count, int) or count < len(traces):
        raise ValueError("Invalid differential trace count")
    dispositions = Counter(str(trace.get("disposition", "UNKNOWN")) for trace in traces)
    if set(dispositions) & SUCCESS:
        reachable = True
    elif count == len(traces) and count > 0:
        reachable = False
    else:
        reachable = None
    return reachable, count > len(traces), dict(dispositions)


def normalize_reachability_rows(rows):
    normalized = []
    for row in rows:
        candidate, candidate_truncated, candidate_dispositions = _side(row, "Snapshot")
        baseline, baseline_truncated, baseline_dispositions = _side(row, "Reference")
        if candidate is baseline and candidate is not None:
            continue
        change = (
            "added"
            if candidate is True and baseline is False
            else "removed"
            if candidate is False and baseline is True
            else "undetermined"
        )
        normalized.append(
            {
                **row,
                "Change": change,
                "Candidate_Reachable": candidate,
                "Baseline_Reachable": baseline,
                "Evidence_Truncated": candidate_truncated or baseline_truncated,
                "Candidate_Dispositions": candidate_dispositions,
                "Baseline_Dispositions": baseline_dispositions,
            }
        )
    return normalized


QUERIES = {"differentialReachability": differential_reachability}
