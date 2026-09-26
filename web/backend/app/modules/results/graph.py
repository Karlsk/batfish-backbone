import json

from app.contracts.errors import ErrorCode, ServiceError
from app.contracts.results import GraphDTO


def bound_graph(graph, *, max_items, max_bytes):
    payload = {"nodes": [], "edges": [], "edge_type": graph.edge_type, "source": graph.source}

    def encode(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    size = len(encode(payload))
    if size > max_bytes:
        raise ServiceError(ErrorCode.NOT_READY)
    reasons = set()
    kept = set()
    for key, items in [("nodes", graph.nodes), ("edges", graph.edges)]:
        for item in items:
            if key == "edges" and (item.source not in kept or item.target not in kept):
                reasons.add("endpoint_limit")
                continue
            if len(payload[key]) >= max_items:
                reasons.add("node_limit" if key == "nodes" else "edge_limit")
                break
            data = item.model_dump(mode="json")
            increment = len(encode(data)) + bool(payload[key])
            if size + increment > max_bytes:
                reasons.add("byte_limit")
                break
            payload[key].append(data)
            size += increment
            if key == "nodes":
                kept.add(item.id)
    return payload, sorted(reasons)


def select_graph(graph, *, focus_node=None, hops=1, limit=200, stored_truncated=False):
    if not 1 <= limit <= 200 or not 0 <= hops <= 5:
        raise ServiceError(ErrorCode.VALIDATION_ERROR)
    nodes = {node.id: node for node in graph.nodes}
    if focus_node is not None and focus_node not in nodes:
        raise ServiceError(ErrorCode.NOT_FOUND)
    distance = dict.fromkeys(nodes, 0)
    if focus_node is not None:
        neighbors = {node: set() for node in nodes}
        for edge in graph.edges:
            neighbors[edge.source].add(edge.target)
            neighbors[edge.target].add(edge.source)
        distance, frontier = {focus_node: 0}, {focus_node}
        for depth in range(1, hops + 1):
            frontier = {other for node in frontier for other in neighbors[node]} - distance.keys()
            distance.update(dict.fromkeys(frontier, depth))
    ordered = sorted(distance, key=lambda node: (distance[node], node))
    selected = set(ordered[:limit])
    eligible = [edge for edge in graph.edges if edge.source in distance and edge.target in distance]
    edges = [edge for edge in eligible if edge.source in selected and edge.target in selected][
        :limit
    ]
    return GraphDTO(
        nodes=tuple(nodes[node] for node in ordered[:limit]),
        edges=tuple(edges),
        edge_type=graph.edge_type,
        source=graph.source,
        scope={
            "focus_node": focus_node,
            "hops": hops if focus_node is not None else None,
            "limit": limit,
            "neighbor_direction": "both",
            "stored_nodes": len(nodes),
            "stored_edges": len(graph.edges),
            "matched_nodes": len(distance),
            "matched_edges": len(eligible),
            "returned_nodes": len(selected),
            "returned_edges": len(edges),
            "storage_truncated": stored_truncated,
        },
        truncated=stored_truncated or len(ordered) > len(selected) or len(eligible) > len(edges),
    )
