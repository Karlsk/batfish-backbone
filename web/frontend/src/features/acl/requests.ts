import type { components } from "../../api/schema";
import { ipv4 } from "../routing/requests";

type Protocol =
  components["schemas"]["FilterTestOptions"]["ip_protocols"][number];
export type FilterDraft = {
  nodeMode: "literal" | "expression";
  node: string;
  nodeExpression: string;
  filterMode: "literal" | "expression";
  filter: string;
  filterExpression: string;
  source: string;
  destination: string;
  protocols: Protocol[];
  sourcePorts: string;
  destinationPorts: string;
};

export const defaultFilterDraft = (): FilterDraft => ({
  nodeMode: "literal",
  node: "",
  nodeExpression: "",
  filterMode: "literal",
  filter: "",
  filterExpression: "",
  source: "",
  destination: "",
  protocols: ["icmp"],
  sourcePorts: "",
  destinationPorts: "",
});

function parsePorts(value: string): number[] | null {
  if (!value.trim()) return null;
  const parts = value.trim().split(/[,\s]+/);
  if (
    parts.length > 100 ||
    parts.some((part) => !/^\d+$/.test(part) || Number(part) > 65535)
  )
    throw new Error("端口必须为 0～65535 的整数，最多100个，用逗号分隔。");
  return [...new Set(parts.map(Number))];
}

export function buildFilterTest(
  draft: FilterDraft,
): components["schemas"]["FilterTestRequest"] {
  const node =
    draft.nodeMode === "literal"
      ? draft.node.trim()
      : draft.nodeExpression.trim();
  const filter =
    draft.filterMode === "literal"
      ? draft.filter.trim()
      : draft.filterExpression.trim();
  if (!node) throw new Error("请选择设备或输入设备表达式。");
  if (!filter) throw new Error("请选择 ACL 或输入 ACL 表达式。");
  if (!ipv4(draft.source.trim()) || !ipv4(draft.destination.trim()))
    throw new Error("请输入有效的源和目标 IPv4 地址。");
  if (!draft.protocols.length) throw new Error("至少选择一个 IP 协议。");
  const sourcePorts = parsePorts(draft.sourcePorts);
  const destinationPorts = parsePorts(draft.destinationPorts);
  if (
    (sourcePorts || destinationPorts) &&
    draft.protocols.some((protocol) => protocol !== "tcp" && protocol !== "udp")
  )
    throw new Error("填写端口时，协议只能选择 TCP 或 UDP。");
  return {
    source_ip: draft.source.trim(),
    destination_ip: draft.destination.trim(),
    nodes:
      draft.nodeMode === "literal"
        ? { mode: "literal", values: [node] }
        : { mode: "expression", expression: node },
    filters:
      draft.filterMode === "literal"
        ? { mode: "literal", values: [filter] }
        : { mode: "expression", expression: filter },
    options: {
      ip_protocols: draft.protocols,
      source_ports: sourcePorts,
      destination_ports: destinationPorts,
    },
  };
}
