import type { components } from "../../api/schema";
import { ipv4 } from "../routing/requests";
import { traceDefaults, traceProtocols } from "../inventory/catalog";
export type TraceDraft = {
  mode: "literal" | "expression";
  node: string;
  iface: string;
  expression: string;
  destination: string;
  source: string;
  protocols: components["schemas"]["TraceOptions"]["ip_protocols"];
  sourcePorts: string;
  ports: string;
  maxTraces: number;
  ignoreFilters: boolean;
};
export const defaultTrace = (): TraceDraft => ({
  mode: "literal",
  node: "",
  iface: "",
  expression: "",
  destination: "",
  source: "",
  protocols: [...traceDefaults.ip_protocols],
  sourcePorts: "",
  ports: "",
  maxTraces: traceDefaults.max_traces,
  ignoreFilters: traceDefaults.ignore_filters,
});

export function traceFromAcl(
  value: unknown,
  networkId: string,
  snapshotId: string,
): TraceDraft {
  const draft = defaultTrace();
  if (!value || typeof value !== "object" || Array.isArray(value)) return draft;
  const preset = value as Record<string, unknown>;
  if (preset.networkId !== networkId || preset.snapshotId !== snapshotId)
    return draft;
  if (
    typeof preset.source !== "string" ||
    !ipv4(preset.source) ||
    typeof preset.destination !== "string" ||
    !ipv4(preset.destination)
  )
    return draft;
  draft.source = preset.source;
  draft.destination = preset.destination;
  const options = preset.options;
  if (!options || typeof options !== "object" || Array.isArray(options))
    return draft;
  const typed = options as Record<string, unknown>;
  if (
    Array.isArray(typed.ip_protocols) &&
    typed.ip_protocols.length &&
    typed.ip_protocols.every((item) => traceProtocols.includes(item))
  )
    draft.protocols = typed.ip_protocols;
  function portText(value: unknown) {
    return Array.isArray(value) &&
      value.length <= 100 &&
      value.every(
        (item) => Number.isInteger(item) && item >= 0 && item <= 65535,
      )
      ? value.join(",")
      : "";
  }
  draft.sourcePorts = portText(typed.source_ports);
  draft.ports = portText(typed.destination_ports);
  return draft;
}
function literal(name: string) {
  return `/^(?:${Array.from(name)
    .map((c) => `\\x{${c.codePointAt(0)!.toString(16)}}`)
    .join("")})$/`;
}
export function literalLocation(node: string, iface: string) {
  return `${literal(node)}${iface ? `[${literal(iface)}]` : ""}`;
}
function ports(value: string) {
  if (!value.trim()) return null;
  const values = value.trim().split(/[,\s]+/);
  if (
    values.length > 100 ||
    values.some((v) => !/^\d+$/.test(v) || Number(v) > 65535)
  )
    throw new Error("端口必须为 0～65535 的整数，最多100个，用逗号分隔。");
  return [...new Set(values.map(Number))];
}
export function buildTrace(
  d: TraceDraft,
): components["schemas"]["TraceRequest"] {
  if (!ipv4(d.destination.trim()))
    throw new Error("请输入有效的目标 IPv4 地址。");
  if (d.source.trim() && !ipv4(d.source.trim()))
    throw new Error("源地址必须是 IPv4 地址。");
  if (d.mode === "literal" && !d.node.trim())
    throw new Error("请选择起点设备。");
  if (d.mode === "expression" && !d.expression.trim())
    throw new Error("请输入起点表达式。");
  if (!d.protocols.length) throw new Error("至少选择一个 IP 协议。");
  if (!Number.isInteger(d.maxTraces) || d.maxTraces < 1 || d.maxTraces > 20)
    throw new Error("每个 Flow 最多展示路径数必须为 1～20。");
  const sourcePorts = ports(d.sourcePorts),
    destinationPorts = ports(d.ports);
  if (
    (sourcePorts || destinationPorts) &&
    d.protocols.some((p) => p !== "tcp" && p !== "udp")
  )
    throw new Error("填写端口时，协议只能选择 TCP 或 UDP。");
  return {
    start_location:
      d.mode === "expression"
        ? d.expression.trim()
        : literalLocation(d.node.trim(), d.iface.trim()),
    destination_ip: d.destination.trim(),
    options: {
      source_ip: d.source.trim() || null,
      ip_protocols: d.protocols,
      source_ports: sourcePorts,
      destination_ports: destinationPorts,
      max_traces: d.maxTraces,
      ignore_filters: d.ignoreFilters,
    },
  };
}
