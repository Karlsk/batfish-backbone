import { Alert, Card, Tag } from "antd";
import type { components } from "../api/schema";
export function ResultSummary({
  result,
}: {
  result: components["schemas"]["ResultEnvelope"];
}) {
  const warnings = [...result.warnings];
  const quality = result.summary.quality;
  if (quality && typeof quality === "object" && !Array.isArray(quality)) {
    const data = quality as Record<string, unknown>;
    const statuses = data.parse_statuses;
    if (
      Number(data.issue_count ?? 0) > 0 ||
      (Array.isArray(statuses) &&
        statuses.some((status) => status !== "PASSED"))
    )
      warnings.unshift(
        "此快照存在解析问题或部分解析，请先查看快照诊断；结果可能不完整。",
      );
  }
  if (result.coverage !== "complete")
    warnings.unshift(
      result.coverage === "limited"
        ? "模型覆盖有限，结论仅适用于已支持的能力。"
        : "模型覆盖范围尚未确认。",
    );
  if (result.truncated)
    warnings.push(`结果已截断：${result.truncation_reason}`);
  if (result.summary.ignore_filters === true)
    warnings.push("本次推演忽略了 ACL 过滤规则。");
  return (
    <Card title="结果摘要" className="result-summary">
      <div className="summary-metrics">
        <div className="summary-metric">
          <span className="summary-label">已返回记录</span>
          <strong className="summary-value">
            {String(result.summary.returned_rows ?? 0)}
            <small>项</small>
          </strong>
        </div>
        <div className="summary-metric">
          <span className="summary-label">结果类型</span>
          <Tag color="blue">
            {result.kind === "traces" ? "路径推演" : "分析结果"}
          </Tag>
        </div>
        <div className="summary-metric">
          <span className="summary-label">生成时间</span>
          <span>{new Date(result.created_at).toLocaleString("zh-CN")}</span>
        </div>
      </div>
      <p className="result-source">来源快照：{result.context.snapshot_id}</p>
      {[...new Set(warnings)].map((warning) => (
        <Alert
          key={warning}
          type="warning"
          showIcon
          title={warning}
          className="summary-warning"
        />
      ))}
    </Card>
  );
}
