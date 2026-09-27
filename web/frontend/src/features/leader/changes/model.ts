import type { components } from "../../../api/schema";

type Json = components["schemas"]["JsonValue"];
type Result = components["schemas"]["ResultEnvelope"];
type Concern = components["schemas"]["ConcernDTO"];

export type ChangeTemplateId =
  | "change-config"
  | "change-routes"
  | "change-reachability";
export type ChangeDraft = {
  comparison_id?: string;
  network?: string;
  nodes?: string;
  start_location?: string;
  destination_ips?: string;
  source_ip?: string;
  protocol?: string;
  destination_port?: number | null;
  max_traces?: number | null;
};
export type FaultDraft = {
  display_name?: string;
  nodes?: string;
  interfaces?: { node: string; interface: string }[];
};

const names = (value?: string) =>
  value
    ?.split(",")
    .map((item) => item.trim())
    .filter(Boolean) ?? [];

export function prepareChangeCheck(
  template: ChangeTemplateId,
  draft: ChangeDraft,
) {
  if (!draft.comparison_id?.trim()) throw new Error("请选择固定比较记录");
  const scope: Record<string, Json> = { comparison_id: draft.comparison_id };
  const options: Record<string, Json> = {};
  if (template === "change-routes") {
    if (!draft.network?.trim()) throw new Error("请填写要比较的 IPv4 网段");
    scope.network = draft.network.trim();
    const nodes = names(draft.nodes);
    if (nodes.length > 100) throw new Error("一次最多选择 100 台设备");
    if (nodes.length) scope.nodes = { mode: "literal", values: nodes };
  }
  if (template === "change-reachability") {
    if (!draft.start_location?.trim()) throw new Error("请填写流量起点");
    if (!draft.destination_ips?.trim()) throw new Error("请填写目的 IPv4 范围");
    scope.start_location = draft.start_location.trim();
    scope.destination_ips = draft.destination_ips.trim();
    if (draft.source_ip?.trim()) options.source_ips = draft.source_ip.trim();
    if (draft.protocol) options.ip_protocols = [draft.protocol];
    if (draft.destination_port != null) {
      if (draft.protocol !== "tcp" && draft.protocol !== "udp")
        throw new Error("目标端口只适用于 TCP/UDP");
      options.destination_ports = [draft.destination_port];
    }
    if (draft.max_traces != null) options.max_traces = draft.max_traces;
  }
  return { scope, options };
}

export function prepareFaultCheck(draft: FaultDraft) {
  if (!draft.display_name?.trim()) throw new Error("请填写故障方案名称");
  const nodes = names(draft.nodes);
  const interfaces = draft.interfaces ?? [];
  if (!nodes.length && !interfaces.length)
    throw new Error("请至少明确选择一台设备或一个接口");
  if (nodes.length > 100 || interfaces.length > 500)
    throw new Error("设备或接口数量超出单次上限");
  if (interfaces.some((item) => !item.node.trim() || !item.interface.trim()))
    throw new Error("接口必须同时指定设备和接口名");
  return {
    scope: {
      display_name: draft.display_name.trim(),
      deactivate_nodes: nodes,
      deactivate_interfaces: interfaces,
    },
    options: {},
  };
}

const count = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

export function changeConclusion(
  template: ChangeTemplateId,
  result: Result,
  rows?: Record<string, unknown>[],
) {
  const summary = result.summary;
  const facts: string[] = [];
  const warnings: string[] = [];
  let headline: string;
  if (template === "change-config") {
    const total = count(summary.total_files);
    headline =
      total === 0
        ? "两份快照未发现配置文本差异"
        : `已发现 ${total ?? "若干"} 个配置文件变化`;
    facts.push(
      `候选新增 ${count(summary.added) ?? "未知"} 个、基线消失 ${count(summary.removed) ?? "未知"} 个、内容变化 ${count(summary.changed) ?? "未知"} 个`,
    );
    warnings.push(
      "配置文本变化不等于网络行为变化；无文本差异也不能证明策略等价。",
    );
  } else if (template === "change-routes") {
    const total = count(summary.returned_rows);
    headline =
      total === 0
        ? "所选范围未返回模型路由变化"
        : `已保存 ${total ?? "若干"} 条模型路由变化`;
    if (rows) {
      const values = new Map<string, number>();
      for (const row of rows) {
        const key = String(row.Change ?? "undetermined");
        values.set(key, (values.get(key) ?? 0) + 1);
      }
      for (const [key, value] of values)
        facts.push(
          `${key === "added" ? "候选新增" : key === "removed" ? "候选消失" : "变化待确认"}：${value} 条（当前页）`,
        );
    }
    warnings.push("只检查明确网段；没有返回变化不代表全网或现场转发一致。");
  } else {
    const examples = count(summary.returned_examples);
    headline =
      examples === 0
        ? "所选范围未返回可达性变化样本"
        : `已保存 ${examples ?? "若干"} 条可达性变化样本`;
    const changes = summary.changes;
    if (changes && typeof changes === "object" && !Array.isArray(changes))
      for (const [kind, value] of Object.entries(changes))
        facts.push(`${kind}：${count(value) ?? "未知"} 条已保存样本`);
    warnings.push(
      "SDK 样本不等于全部业务流量，不能推断全部业务影响或现场中断。",
    );
  }
  if (result.coverage !== "complete")
    warnings.push("模型覆盖有限或待确认，变化结论只适用于已支持的范围。");
  if (result.truncated)
    warnings.push(`结果已截断：${result.truncation_reason ?? "超出保存上限"}`);
  warnings.push(...result.warnings);
  return { headline, facts, warnings: [...new Set(warnings)] };
}

export function relevantConcern(
  concern: Concern,
  start: string,
  destination: string,
  protocol?: string,
  destinationPort?: number | null,
  sourceIp?: string,
) {
  return concern.flows.some(
    (flow) =>
      flow.start_location === start &&
      flow.destination_ip === destination &&
      (!flow.protocol || flow.protocol === protocol) &&
      (!flow.source_ip || flow.source_ip === sourceIp) &&
      (flow.destination_port == null ||
        flow.destination_port === destinationPort),
  );
}

export function canCompareDerived(runStatus: string, snapshotStatus?: string) {
  return (
    runStatus === "succeeded" &&
    (snapshotStatus === "ready" || snapshotStatus === "ready_with_warnings")
  );
}
