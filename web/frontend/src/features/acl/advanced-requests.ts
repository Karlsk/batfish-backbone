import type { components } from "../../api/schema";
import { traceProtocols } from "../inventory/catalog";
import { ipv4 } from "../routing/requests";
import { defaultFilterDraft, type FilterDraft } from "./requests";

type Protocol = NonNullable<
  components["schemas"]["SearchHeaders"]["ip_protocols"]
>[number];
type Action = components["schemas"]["SearchFiltersRequest"]["action"];

export type SearchDraft = {
  nodes: string[];
  filters: string[];
  source: string;
  destination: string;
  action: Action;
  lineNumber: string;
  protocols: Protocol[];
  sourcePorts: string;
  destinationPorts: string;
};

export type ReachabilityDraft = {
  nodes: string[];
  filters: string[];
  ignoreComposites: boolean;
};

export const defaultSearchDraft = (): SearchDraft => ({
  nodes: [],
  filters: [],
  source: "",
  destination: "",
  action: "permit",
  lineNumber: "",
  protocols: [],
  sourcePorts: "",
  destinationPorts: "",
});

export const defaultReachabilityDraft = (): ReachabilityDraft => ({
  nodes: [],
  filters: [],
  ignoreComposites: true,
});

function scope(values: string[], label: string) {
  if (!values.length) throw new Error(`请选择${label}。`);
  if (values.length > 10) throw new Error(`${label}最多选择10项。`);
  const names = values.map((value) => value.trim());
  if (
    names.some(
      (value) => !value || value.length > 255 || /[\x00-\x1f\x7f]/.test(value),
    )
  )
    throw new Error(`${label}名称无效。`);
  return { mode: "literal" as const, values: [...new Set(names)] };
}

function ports(text: string) {
  if (!text.trim()) return null;
  const values = text.trim().split(/[,\s]+/);
  if (
    values.length > 100 ||
    values.some((value) => !/^\d+$/.test(value) || Number(value) > 65535)
  )
    throw new Error("端口必须为0～65535的整数，最多100项。");
  return [...new Set(values.map(Number))];
}

export function buildFilterSearch(
  draft: SearchDraft,
): components["schemas"]["SearchFiltersRequest"] {
  const nodes = scope(draft.nodes, "设备");
  const filters = scope(draft.filters, "ACL");
  const source = draft.source.trim();
  const destination = draft.destination.trim();
  if (!ipv4(source) || !ipv4(destination))
    throw new Error("请输入有效的源和目标 IPv4 地址。");
  const sourcePorts = ports(draft.sourcePorts);
  const destinationPorts = ports(draft.destinationPorts);
  if (
    (sourcePorts || destinationPorts) &&
    (!draft.protocols.length ||
      draft.protocols.some((value) => value !== "tcp" && value !== "udp"))
  )
    throw new Error("填写端口时，协议只能选择 TCP 或 UDP。");
  if (
    draft.action === "match_line" &&
    (!/^\d+$/.test(draft.lineNumber.trim()) ||
      Number(draft.lineNumber) > 100000)
  )
    throw new Error("请输入0～100000的规则行号。");
  return {
    nodes,
    filters,
    action: draft.action,
    options: {
      headers: {
        source_ip: source,
        destination_ip: destination,
        ...(draft.protocols.length ? { ip_protocols: draft.protocols } : {}),
        ...(sourcePorts ? { source_ports: sourcePorts } : {}),
        ...(destinationPorts ? { destination_ports: destinationPorts } : {}),
      },
      ...(draft.action === "match_line"
        ? { line_number: Number(draft.lineNumber) }
        : {}),
    },
  };
}

export function buildRuleReachability(
  draft: ReachabilityDraft,
): components["schemas"]["FilterLineReachabilityRequest"] {
  return {
    nodes: scope(draft.nodes, "设备"),
    filters: scope(draft.filters, "ACL"),
    options: { ignore_composites: draft.ignoreComposites },
  };
}

export function filterDraftFromWitness(
  value: unknown,
  networkId: string,
  snapshotId: string,
): FilterDraft | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const preset = value as Record<string, unknown>;
  if (preset.networkId !== networkId || preset.snapshotId !== snapshotId)
    return null;
  const flow = preset.flow;
  if (!flow || typeof flow !== "object" || Array.isArray(flow)) return null;
  const record = flow as Record<string, unknown>;
  const protocol =
    typeof record.ipProtocol === "string"
      ? record.ipProtocol.toLowerCase().replace(/^ahp$/, "ah")
      : "";
  if (
    typeof preset.node !== "string" ||
    !preset.node ||
    typeof preset.filter !== "string" ||
    !preset.filter ||
    typeof record.srcIp !== "string" ||
    !ipv4(record.srcIp) ||
    typeof record.dstIp !== "string" ||
    !ipv4(record.dstIp) ||
    !traceProtocols.includes(protocol as Protocol)
  )
    return null;
  const sourcePort = record.srcPort;
  const destinationPort = record.dstPort;
  const validPort = (port: unknown) =>
    port == null ||
    (typeof port === "number" &&
      Number.isInteger(port) &&
      port >= 0 &&
      port <= 65535);
  if (!validPort(sourcePort) || !validPort(destinationPort)) return null;
  if (
    (sourcePort != null || destinationPort != null) &&
    protocol !== "tcp" &&
    protocol !== "udp"
  )
    return null;
  return {
    ...defaultFilterDraft(),
    node: preset.node,
    filter: preset.filter,
    source: record.srcIp,
    destination: record.dstIp,
    protocols: [protocol as Protocol],
    sourcePorts: sourcePort == null ? "" : String(sourcePort),
    destinationPorts: destinationPort == null ? "" : String(destinationPort),
  };
}
