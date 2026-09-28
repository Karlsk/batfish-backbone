import type { components } from "../../../api/schema";

type CheckRun = components["schemas"]["CheckRun"];
type BriefingSection = components["schemas"]["BriefingSection"];
export type RunPick = Pick<
  CheckRun,
  | "id"
  | "template_id"
  | "status"
  | "snapshot_id"
  | "result_ids"
  | "effective_parameters"
  | "concern_id"
  | "concern_version"
>;

export function reportableRuns(runs: RunPick[], snapshotId: string) {
  return runs.filter(
    (run) =>
      run.status === "succeeded" &&
      run.snapshot_id === snapshotId &&
      run.result_ids.length > 0,
  );
}

export function selectedSources(runs: RunPick[]) {
  const resultIds = Array.from(new Set(runs.flatMap((run) => run.result_ids)));
  if (!resultIds.length || resultIds.length > 20)
    throw new Error("请选择 1～20 个已完成的检查结果");
  const comparisons = Array.from(
    new Set(
      runs
        .map((run) => run.effective_parameters.comparison_id)
        .filter((value): value is string => typeof value === "string"),
    ),
  );
  if (comparisons.length > 1) throw new Error("不能混合不同的固定比较");
  const concernPairs = Array.from(
    new Set(
      runs
        .filter((run) => run.concern_id && run.concern_version)
        .map((run) => `${run.concern_id}:${run.concern_version}`),
    ),
  );
  const sameConcern =
    concernPairs.length === 1 &&
    runs.every(
      (run) =>
        run.concern_id &&
        run.concern_version &&
        `${run.concern_id}:${run.concern_version}` === concernPairs[0],
    );
  const runWithConcern = sameConcern
    ? runs.find((run) => run.concern_id && run.concern_version)
    : undefined;
  return {
    resultIds,
    comparisonId: comparisons[0] ?? null,
    concernId: runWithConcern?.concern_id ?? null,
    concernVersion: runWithConcern?.concern_version ?? null,
  };
}

const labels: Record<string, string> = {
  added: "新增",
  removed: "消失",
  changed: "变化",
  node_count: "设备数",
  device_count: "设备数",
  edge_count: "推导关系",
  total_files: "配置文件",
  returned_files: "展示文件",
  total_rows: "结果总行数",
  returned_rows: "展示行数",
  row_count: "结果行数",
  total_flows: "流量样本",
};
const priority = Object.keys(labels);

export function summaryFacts(summary: BriefingSection["summary"]) {
  const keys = [
    ...priority.filter((key) => key in summary),
    ...Object.keys(summary).filter((key) => !(key in labels)),
  ];
  return keys
    .filter((key) =>
      ["number", "string", "boolean"].includes(typeof summary[key]),
    )
    .slice(0, 4)
    .map((key) => ({ label: labels[key] ?? key, value: String(summary[key]) }));
}

export function briefingIndicators(
  section: Pick<
    BriefingSection,
    "coverage" | "truncated" | "truncation_reason" | "warnings"
  >,
) {
  return [
    ...(section.coverage === "limited"
      ? ["模型覆盖有限"]
      : section.coverage === "unknown"
        ? ["模型覆盖未知"]
        : []),
    ...(section.truncated
      ? [`结果已截断：${section.truncation_reason ?? "原因未知"}`]
      : []),
    ...section.warnings,
  ];
}

export function readableWarning(warning: string) {
  if (!warning.startsWith("{'vendor':")) return warning;
  const read = (field: string) =>
    new RegExp(`'${field}': '([^']*)'`).exec(warning)?.[1];
  const vendor = read("vendor");
  const capability = read("capability");
  const status = read("status");
  const description = read("description");
  if (!vendor || !capability || !status || !description) return warning;
  const statusLabel =
    { unsupported: "未支持", unknown: "未验证", supported: "已支持" }[status] ??
    status;
  return `${vendor} · ${capability}：${statusLabel}；${description}`;
}
