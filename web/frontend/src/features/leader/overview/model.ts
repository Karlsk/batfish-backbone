import type { components } from "../../../api/schema";

type Card = components["schemas"]["NetworkOverview"];

const readinessLabels: Record<Card["readiness"], string> = {
  pending: "待准备",
  ready: "快照就绪",
  warning: "需关注",
};
const checkLabels: Record<Card["check_state"], string> = {
  not_checked: "未检查",
  queued: "等待检查",
  running: "检查中",
  succeeded: "结果可读",
  failed: "检查失败",
  cancelled: "已取消",
  interrupted: "检查中断",
  result_unavailable: "结果暂不可读",
  result_available: "已有结果",
};

export function describeNetwork(card: Card) {
  const warnings: string[] = [];
  if (
    card.latest_snapshot &&
    card.latest_ready_snapshot &&
    card.latest_snapshot.id !== card.latest_ready_snapshot.id
  )
    warnings.push("最新快照尚未就绪，使用上一就绪版本");
  if (card.latest_ready_snapshot?.status === "ready_with_warnings")
    warnings.push("配置解析存在警告");
  const limits = card.latest_ready_snapshot?.model_limit_count ?? 0;
  if (limits) warnings.push(`${limits} 项模型限制`);
  if (card.latest_result?.coverage === "limited") warnings.push("覆盖有限");
  if (card.latest_result?.coverage === "unknown") warnings.push("覆盖范围未知");
  if (card.latest_result?.truncated) warnings.push("结果已截断");
  const resultWarnings = card.latest_result?.warning_count ?? 0;
  if (resultWarnings) warnings.push(`${resultWarnings} 条结果警告`);
  const negative = ["failed", "interrupted", "result_unavailable"].includes(
    card.check_state,
  );
  const tone =
    warnings.length || card.readiness === "warning" || negative
      ? "warning"
      : card.readiness === "ready" &&
          card.check_state === "succeeded" &&
          card.latest_result?.coverage === "complete"
        ? "good"
        : "neutral";
  return {
    readiness: readinessLabels[card.readiness],
    check: checkLabels[card.check_state],
    warnings,
    tone,
  } as const;
}
