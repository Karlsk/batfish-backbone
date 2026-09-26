import type { components } from "../../api/schema";
import type { ElementDefinition } from "cytoscape";
export type Graph = components["schemas"]["GraphDTO"];
export type GraphSelection = { kind: "node" | "edge"; id: string };
export const views = {
  layer3: "三层推导",
  bgp: "BGP 关系",
  ospf: "OSPF 关系",
  isis: "ISIS 关系",
} as const;
export function prepareGraph(graph: Graph) {
  const nodes = graph.nodes.slice(0, 200),
    names = new Set(nodes.map((n) => n.id));
  const edges = graph.edges
    .filter((e) => names.has(e.source) && names.has(e.target))
    .slice(0, 200);
  const elements: ElementDefinition[] = [
    ...nodes.map((n) => ({
      data: { id: "node:" + n.id, rawId: n.id, label: n.label },
    })),
    ...edges.map((e) => ({
      data: {
        id: "edge:" + e.id,
        rawId: e.id,
        source: "node:" + e.source,
        target: "node:" + e.target,
        label: e.source_interface ?? e.edge_type,
      },
    })),
  ];
  return {
    nodes,
    edges,
    elements,
    truncated:
      graph.truncated ||
      nodes.length < graph.nodes.length ||
      edges.length < graph.edges.length,
  };
}
