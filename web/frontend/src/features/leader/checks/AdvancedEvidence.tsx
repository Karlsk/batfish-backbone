import { Alert, Card, Empty, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import type { components } from "../../../api/schema";
import { api, unwrap } from "../../../api/client";
import { ErrorState, LoadingState } from "../../../components/States";
import { FocusedGraph } from "../topology/FocusedGraph";
import type { AdvancedTemplateId } from "./advanced";

type Result = components["schemas"]["ResultEnvelope"];
type TablePage = components["schemas"]["TablePage"];

const display = (value: unknown) => {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "name" in value)
    return String(value.name);
  return value == null ? "未记录" : String(value);
};

export function AdvancedEvidence({
  template,
  result,
  rows,
  error,
  pending,
  retry,
}: {
  template: AdvancedTemplateId;
  result: Result;
  rows?: TablePage;
  error: unknown;
  pending: boolean;
  retry: () => void;
}) {
  if (template === "topology") return <FocusedGraph result={result} />;
  return (
    <Card
      title={template === "bgp" ? "04 / BGP 会话证据" : "04 / ACL 规则证据"}
      className="leader-checks-panel"
    >
      {error ? (
        <ErrorState error={error} retry={retry} />
      ) : pending ? (
        <LoadingState />
      ) : rows ? (
        <>
          <p className="leader-checks-note">
            已读取前 {rows.rows.length} 条，共 {rows.total}{" "}
            条记录。这里只展示必要字段，完整表格在技术工作台。
          </p>
          {(rows.truncated ||
            rows.total > rows.rows.length ||
            result.truncated) && (
            <Alert
              type="warning"
              title="结果分页或截断；当前证据不代表全部会话或 ACL。"
            />
          )}
          {rows.rows.length ? (
            <div className="leader-advanced-rows">
              {rows.rows.slice(0, 20).map((row, index) => (
                <div key={index} className="leader-advanced-row">
                  {template === "bgp" ? (
                    <>
                      <strong>
                        {display(row.Node)} → {display(row.Remote_Node)}
                      </strong>
                      <Tag>
                        {display(
                          row.Established_Status ?? row.Configured_Status,
                        )}
                      </Tag>
                    </>
                  ) : (
                    <>
                      <strong>{display(row.Filter)}</strong>
                      <Tag color={row.Action === "PERMIT" ? "blue" : "gold"}>
                        {row.Implicit_Deny === true
                          ? "隐式拒绝"
                          : row.Action === "PERMIT"
                            ? "局部放行"
                            : row.Action === "DENY"
                              ? "明确拒绝"
                              : "动作待确认"}
                      </Tag>
                    </>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <Empty description="此范围未返回匹配记录" />
          )}
        </>
      ) : null}
    </Card>
  );
}

export function ExpertCapabilities() {
  const capabilities = useQuery({
    queryKey: ["leader-expert-capabilities"],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/capabilities", { signal })),
  });
  const advanced = capabilities.data?.filter((item) => item.stage >= 2) ?? [];
  return (
    <Card title="更多专家能力" className="leader-checks-panel">
      <p className="leader-checks-note">
        以下仅列出服务端登记的能力。需要自定义查询时，在技术工作台使用完整参数与原始结果。
      </p>
      {capabilities.isError && (
        <ErrorState
          error={capabilities.error}
          retry={() => void capabilities.refetch()}
        />
      )}
      {capabilities.isPending && <LoadingState />}
      {capabilities.data && (
        <div className="leader-capabilities">
          {advanced.map((item) => (
            <div key={item.id}>
              <strong>{item.label}</strong>
              <span>{item.id}</span>
              <Tag color={item.enabled ? "blue" : "gold"}>
                {item.enabled ? "已登记" : "暂不可用"}
              </Tag>
            </div>
          ))}
          {!advanced.length && <Empty description="当前没有登记的高级能力" />}
        </div>
      )}
    </Card>
  );
}
