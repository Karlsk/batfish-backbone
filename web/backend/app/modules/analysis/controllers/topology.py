import hashlib
import json

from app.contracts.results import GraphData, GraphEdge, GraphNode
from app.modules.analysis.controllers.inventory import selector

SOURCES = {"layer3": "layer3Edges", "bgp": "bgpEdges", "ospf": "ospfEdges", "isis": "isisEdges"}


def kwargs(parameters):
    return {
        sdk: selector(parameters["options"][key])
        for key, sdk in [("nodes", "nodes"), ("remote_nodes", "remoteNodes")]
        if parameters["options"][key] is not None
    }


QUERIES = {
    "layer3Edges": lambda session, parameters: session.q.layer3Edges(**kwargs(parameters)),
    "bgpEdges": lambda session, parameters: session.q.bgpEdges(**kwargs(parameters)),
    "ospfEdges": lambda session, parameters: session.q.ospfEdges(**kwargs(parameters)),
    "isisEdges": lambda session, parameters: session.q.isisEdges(**kwargs(parameters)),
}


def query_plan(parameters):
    options = parameters["options"]
    selections = [options["nodes"], options["remote_nodes"]]
    if None in selections:
        selections = [None]
    elif selections[0] == selections[1]:
        selections = selections[:1]
    return [
        (
            "nodeProperties",
            {"options": {"nodes": selection, "properties": ["Configuration_Format"]}},
        )
        for selection in selections
    ] + [(SOURCES[parameters["view"]], parameters)]


def name(value):
    return value["name"] if isinstance(value, dict) else str(value)


def normalize_graph(view, node_rows, edge_rows):
    nodes = {
        name(row["Node"]): GraphNode(id=name(row["Node"]), label=name(row["Node"]), properties=row)
        for row in node_rows
    }
    edges = {}
    for row in edge_rows:
        if view == "bgp":
            source, target = name(row["Node"]), name(row["Remote_Node"])
            source_interface, target_interface = row.get("Interface"), row.get("Remote_Interface")
        else:
            source, target = row["Interface"]["hostname"], row["Remote_Interface"]["hostname"]
            source_interface, target_interface = (
                row["Interface"]["interface"],
                row["Remote_Interface"]["interface"],
            )
        for node in (source, target):
            nodes.setdefault(node, GraphNode(id=node, label=node))
        # Include all original endpoint evidence: IP/AS distinguish parallel BGP peers.
        identifier = hashlib.sha256(
            json.dumps(
                [view, row], sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        edges[identifier] = GraphEdge(
            id=identifier,
            source=source,
            target=target,
            source_interface=source_interface,
            target_interface=target_interface,
            edge_type=view,
            properties=row,
        )
    return GraphData(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        edge_type=view,
        source=SOURCES[view],
    )
