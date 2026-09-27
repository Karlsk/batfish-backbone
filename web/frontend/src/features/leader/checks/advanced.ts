import type { components } from "../../../api/schema";
import { aclDecision } from "../../acl/FilterResult";

type Result = components["schemas"]["ResultEnvelope"];
type Row = Record<string, unknown>;

export type AdvancedTemplateId = "topology" | "bgp" | "acl";
export type AdvancedDraft = {
  view?: "layer3" | "bgp" | "ospf" | "isis";
  mode?: "status" | "compatibility";
  nodes?: string;
  remote_nodes?: string;
  source_ip?: string;
  destination_ip?: string;
  filters?: string;
  protocol?: string;
  destination_port?: number | null;
};

export type AdvancedEvidence = {
  rows: Row[];
  total: number;
  truncated: boolean;
};

const names = (value?: string) =>
  value
    ?.split(",")
    .map((item) => item.trim())
    .filter(Boolean) ?? [];

const selector = (value?: string) => {
  const values = names(value);
  if (values.length > 100) throw new Error("一次最多指定 100 项");
  return values.length ? { mode: "literal", values } : undefined;
};

export function prepareAdvancedCheck(
  template: AdvancedTemplateId,
  draft: AdvancedDraft,
) {
  const scope: Record<string, components["schemas"]["JsonValue"]> = {};
  const options: Record<string, components["schemas"]["JsonValue"]> = {};
  if (template === "acl") {
    if (!draft.source_ip?.trim()) throw new Error("请填写流量源地址");
    if (!draft.destination_ip?.trim()) throw new Error("请填写流量目的地址");
    const filters = selector(draft.filters);
    if (!filters) throw new Error("请填写要检查的 ACL 名称");
    scope.source_ip = draft.source_ip.trim();
    scope.destination_ip = draft.destination_ip.trim();
    scope.filters = filters;
    const nodes = selector(draft.nodes);
    if (nodes) scope.nodes = nodes;
    if (draft.protocol) options.ip_protocols = [draft.protocol];
    if (draft.destination_port != null)
      options.destination_ports = [draft.destination_port];
  } else {
    const nodes = selector(draft.nodes);
    const remoteNodes = selector(draft.remote_nodes);
    if (nodes) options.nodes = nodes;
    if (remoteNodes) options.remote_nodes = remoteNodes;
    if (template === "topology" && draft.view) options.view = draft.view;
    if (template === "bgp" && draft.mode) options.mode = draft.mode;
  }
  return { scope, options };
}

const count = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const relationNames: Record<string, string> = {
  layer3: "三层推导关系",
  bgp: "BGP 协议关系",
  ospf: "OSPF 协议关系",
  isis: "ISIS 协议关系",
};
const sourceNames: Record<string, string> = {
  layer3Edges: "配置模型三层关系",
  bgpEdges: "配置模型 BGP 关系",
  ospfEdges: "配置模型 OSPF 关系",
  isisEdges: "配置模型 ISIS 关系",
};
export const graphTypeLabel = (value: string) => relationNames[value] ?? value;
export const graphSourceLabel = (value: string) => sourceNames[value] ?? value;

const warningLabel = (value: string) =>
  value ===
  "Protocol relations are not session health; missing edges do not prove physical disconnection"
    ? "协议关系不等于实时会话健康；缺少关系边不能证明物理断线。"
    : value;

function bgpMode(result: Result) {
  const request = result.effective_parameters?.request;
  if (!request || typeof request !== "object" || Array.isArray(request))
    return "status";
  const options = (request as Row).options;
  return options &&
    typeof options === "object" &&
    !Array.isArray(options) &&
    (options as Row).mode === "compatibility"
    ? "compatibility"
    : "status";
}

export function describeAdvanced(
  template: AdvancedTemplateId,
  result: Result,
  evidence?: AdvancedEvidence,
) {
  const facts: string[] = [];
  const warnings: string[] = [];
  let headline = "检查结果已生成，正在读取证据";
  if (template === "topology") {
    const nodes = count(result.summary.returned_nodes);
    const edges = count(result.summary.returned_edges);
    headline =
      nodes === null || edges === null
        ? "拓扑关系结果已生成"
        : `已保存 ${nodes} 台设备、${edges} 条模型关系`;
    facts.push(
      `关系类型：${graphTypeLabel(String(result.summary.edge_type ?? "待确认"))}`,
    );
    facts.push(
      `来源：${graphSourceLabel(String(result.summary.source ?? "已保存配置模型"))}`,
    );
    warnings.push("这些关系由配置模型推导，不能证明物理链路或实时流量。");
    if (edges === 0)
      warnings.push("当前范围没有该类型关系，不能据此判断物理断线。");
  } else if (template === "bgp") {
    const mode = bgpMode(result);
    headline =
      mode === "status" ? "BGP 模型会话已计算" : "BGP 配置兼容性已计算";
    facts.push(
      mode === "status" ? "分析模式：模型会话状态" : "分析模式：配置兼容性",
    );
    warnings.push("模型中的 BGP 状态不代表设备实时会话健康。");
    if (evidence) {
      const column =
        mode === "status" ? "Established_Status" : "Configured_Status";
      facts.push(
        `当前展示前 ${evidence.rows.length} 条，共 ${evidence.total} 条已保存记录`,
      );
      const statuses = new Map<string, number>();
      for (const row of evidence.rows) {
        const value = row[column];
        const key = typeof value === "string" ? value : "UNKNOWN";
        statuses.set(key, (statuses.get(key) ?? 0) + 1);
      }
      for (const [status, value] of statuses)
        facts.push(`${column} ${status}：${value} 条（当前页）`);
      if (!evidence.rows.length) headline = "此范围没有匹配的 BGP 模型会话";
    }
  } else {
    warnings.push("ACL 只判断指定规则对明确流量的局部动作，不代表端到端可达。");
    if (evidence) {
      const decision = aclDecision(
        evidence.rows,
        evidence.total,
        evidence.truncated || result.truncated,
      );
      headline = decision.label;
      facts.push(`匹配记录：${evidence.total} 条`);
      if (decision.kind === "mixed")
        warnings.push("不同 ACL 的动作不一致，应逐条查看证据。");
    }
  }
  if (evidence && (evidence.truncated || evidence.total > evidence.rows.length))
    warnings.push("证据分页或截断，当前页面不能概括全部记录。");
  if (result.truncated)
    warnings.push(
      `已保存结果截断：${result.truncation_reason ?? "超出保存范围"}`,
    );
  if (result.coverage !== "complete")
    warnings.push(
      result.coverage === "limited"
        ? "模型覆盖有限，结论只适用于已支持的范围。"
        : "模型覆盖范围待确认，不能推断未建模能力。",
    );
  warnings.push(...result.warnings.map(warningLabel));
  return { headline, facts, warnings: [...new Set(warnings)] };
}
