import { Alert, Card, Space, Tag, Typography } from "antd";
import type { components } from "../api/schema";
export function ResultSummary({
  result,
}: {
  result: components["schemas"]["ResultEnvelope"];
}) {
  const warnings = [...result.warnings];
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
    <Card title="结果摘要">
      <Space wrap>
        <Tag color="blue">
          {result.kind === "traces" ? "路径推演" : "分析结果"}
        </Tag>
        <span>已返回 {String(result.summary.returned_rows ?? 0)} 项</span>
        <Typography.Text type="secondary">
          {new Date(result.created_at).toLocaleString("zh-CN")}
        </Typography.Text>
      </Space>
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
