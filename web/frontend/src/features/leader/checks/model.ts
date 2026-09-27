import type { components } from "../../../api/schema";

type Run = components["schemas"]["CheckRun"];
type Result = components["schemas"]["ResultEnvelope"];

export const runStatusLabels: Record<Run["status"], string> = {
  submitting: "登记中",
  queued: "排队中",
  running: "检查中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "已中断",
  result_unavailable: "结果暂不可读",
};
export const engineStateLabels = {
  idle: "空闲",
  busy: "运行中",
  unknown: "待确认",
} as const;
export const coverageLabels = {
  complete: "完整",
  limited: "有限",
  unknown: "待确认",
} as const;

const dispositionLabels: Record<string, string> = {
  ACCEPTED: "已到达目标",
  DELIVERED_TO_SUBNET: "已交付目标网段",
  EXITS_NETWORK: "离开已建模网络",
  NO_ROUTE: "无匹配路由",
  NULL_ROUTED: "被空路由丢弃",
  DENIED_IN: "入站策略拒绝",
  DENIED_OUT: "出站策略拒绝",
  LOOP: "出现环路",
  NEIGHBOR_UNREACHABLE: "邻居不可达",
  INSUFFICIENT_INFO: "模型信息不足",
};

export type MvpTemplateId =
  | "configuration-quality"
  | "devices"
  | "interfaces"
  | "routes"
  | "lpm-routes"
  | "traceroute";

export type MvpDraft = {
  network?: string;
  ip?: string;
  start_location?: string;
  destination_ip?: string;
  nodes?: string;
  vrfs?: string;
  source_ip?: string;
  protocol?: string;
  destination_port?: number | null;
  max_traces?: number | null;
};

const names = (value?: string) =>
  value
    ?.split(",")
    .map((item) => item.trim())
    .filter(Boolean) ?? [];

export function prepareMvpCheck(template: MvpTemplateId, draft: MvpDraft) {
  const scope: Record<string, components["schemas"]["JsonValue"]> = {};
  const options: Record<string, components["schemas"]["JsonValue"]> = {};
  const nodes = names(draft.nodes);
  if (nodes.length > 100) throw new Error("一次最多指定 100 台设备");
  const selector = nodes.length
    ? { mode: "literal", values: nodes }
    : undefined;
  if (template === "routes") {
    if (!draft.network?.trim()) throw new Error("请填写要检查的 IPv4 网段");
    scope.network = draft.network.trim();
    if (selector) scope.nodes = selector;
  } else if (template === "lpm-routes") {
    if (!draft.ip?.trim()) throw new Error("请填写要查询的 IPv4 地址");
    scope.ip = draft.ip.trim();
    if (selector) scope.nodes = selector;
  } else if (template === "traceroute") {
    if (!draft.start_location?.trim()) throw new Error("请填写起点设备或接口");
    if (!draft.destination_ip?.trim()) throw new Error("请填写目的 IPv4 地址");
    scope.start_location = draft.start_location.trim();
    scope.destination_ip = draft.destination_ip.trim();
    if (draft.source_ip?.trim()) options.source_ip = draft.source_ip.trim();
    if (draft.protocol) options.ip_protocols = [draft.protocol];
    if (draft.destination_port != null)
      options.destination_ports = [draft.destination_port];
    if (draft.max_traces != null) options.max_traces = draft.max_traces;
  } else if (template === "devices" || template === "interfaces") {
    if (selector) options.nodes = selector;
  }
  if (
    (template === "routes" || template === "lpm-routes") &&
    draft.vrfs?.trim()
  ) {
    options.vrfs = { mode: "literal", values: names(draft.vrfs) };
  }
  return { scope, options };
}

const number = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
const list = (value: unknown) => (Array.isArray(value) ? value : []);

export function describeRun(run: Run, result: Result | null) {
  const facts: string[] = [];
  const warnings: string[] = [];
  const quality = run.snapshot_quality;
  const issues = number(quality.issue_count) ?? 0;
  if (issues) warnings.push(`配置解析报告 ${issues} 项问题，请查看解析证据。`);
  if (list(quality.model_limits).length)
    warnings.push(
      `${list(quality.model_limits).length} 项模型限制；不能据此判断未支持的能力。`,
    );
  if (run.jobs.some((job) => job.engine_state === "unknown"))
    warnings.push("引擎状态待确认；不要重复提交检查。");

  if (run.status !== "succeeded") {
    const state: Record<Run["status"], string> = {
      submitting: "正在登记检查",
      queued: "检查已排队",
      running: "检查正在进行",
      succeeded: "检查已完成",
      failed: "检查失败",
      cancelled: "检查已取消",
      interrupted: "检查已中断",
      result_unavailable: "结果暂不可读",
    };
    if (run.error_code) warnings.push(`错误代码：${run.error_code}`);
    return { headline: state[run.status], facts, warnings };
  }

  if (run.template_id === "configuration-quality") {
    const nodeCount = number(quality.node_count);
    if (nodeCount !== null) facts.push(`已解析设备：${nodeCount} 台`);
    facts.push(`解析问题：${issues} 项`);
    const statuses = list(quality.parse_statuses).filter(
      (item) => typeof item === "string",
    );
    if (statuses.length) facts.push(`解析状态：${statuses.join("、")}`);
    return {
      headline: issues ? "配置解析存在问题" : "配置解析记录已生成",
      facts,
      warnings,
    };
  }

  if (!result) {
    warnings.push("任务已完成，正在读取固定结果；若持续不可读请查看任务详情。");
    return { headline: "检查已完成，结果待读取", facts, warnings };
  }
  const summary = result.summary;
  let headline = "检查结果已生成";
  if (result.kind === "traces") {
    const count =
      number(summary.returned_trace_count) ?? number(summary.trace_count);
    headline =
      count === null ? "单向路径推演已生成" : `已保存 ${count} 条单向路径推演`;
    const dispositions = summary.dispositions;
    if (
      dispositions &&
      typeof dispositions === "object" &&
      !Array.isArray(dispositions)
    ) {
      for (const [name, value] of Object.entries(dispositions)) {
        const count = number(value);
        if (count !== null)
          facts.push(
            `${dispositionLabels[name] ?? "其他路径结论"}（${name}）：${count} 条`,
          );
      }
    }
    warnings.push("仅为单向配置模型推演，不证明在线转发或回程。");
    if (!facts.length)
      facts.push("此范围未保存可显示的路径结论，请核对起点与目的地。");
  } else {
    const rows = number(summary.returned_rows);
    if (rows !== null) {
      headline = rows ? `已返回 ${rows} 项模型记录` : "此范围没有返回记录";
      facts.push(`已保存记录：${rows} 项`);
    }
  }
  if (result.coverage === "limited")
    warnings.push("模型覆盖有限，结论只适用于已支持的范围。");
  if (result.coverage === "unknown") warnings.push("模型覆盖范围尚未确认。");
  if (result.truncated)
    warnings.push(`结果已截断：${result.truncation_reason ?? "超出保存范围"}`);
  warnings.push(...result.warnings);
  return { headline, facts, warnings: [...new Set(warnings)] };
}
