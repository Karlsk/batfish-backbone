import { Alert, Card, Empty, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import type { components } from "../../../api/schema";
import { api, unwrap } from "../../../api/client";
import { resourceKey } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ErrorState, LoadingState } from "../../../components/States";
import type { ChangeTemplateId } from "./model";

type Result = components["schemas"]["ResultEnvelope"];
type TablePage = components["schemas"]["TablePage"];
const label: Record<string, string> = {
  added: "候选新增",
  removed: "候选消失",
  changed: "内容变化",
  INCREASED: "可达性增加样本",
  DECREASED: "可达性减少样本",
};
const display = (value: unknown) => {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "name" in value)
    return String(value.name);
  return value == null ? "未记录" : String(value);
};

export function ChangeEvidence({
  template,
  result,
  rows,
  rowError,
  rowPending,
  retryRows,
}: {
  template: ChangeTemplateId;
  result: Result;
  rows?: TablePage;
  rowError: unknown;
  rowPending: boolean;
  retryRows: () => void;
}) {
  const session = useSession();
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const files = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "leader-change-files",
      {},
      result.id,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/diff/files", {
          signal,
          params: {
            path: { result_id: result.id },
            query: { offset: 0, limit: 200 },
          },
        }),
      ),
    enabled: template === "change-config",
  });
  const total = template === "change-config" ? files.data?.total : rows?.total;
  return (
    <Card title="04 / 已保存的变化证据" className="leader-checks-panel">
      <p className="leader-checks-note">
        只展示本次固定比较和显式范围内的首批证据；文件行、路由属性和双侧路径在技术详情中按需展开。
      </p>
      {template === "change-config" ? (
        files.isError ? (
          <ErrorState error={files.error} retry={() => void files.refetch()} />
        ) : files.isPending ? (
          <LoadingState />
        ) : files.data?.items.length ? (
          <div className="leader-advanced-rows">
            {files.data.items.slice(0, 20).map((item) => (
              <div key={item.file_id} className="leader-advanced-row">
                <strong>{item.path}</strong>
                <Tag>{label[item.change] ?? item.change}</Tag>
              </div>
            ))}
          </div>
        ) : (
          <Empty description="这两份快照未返回配置文本差异" />
        )
      ) : rowError ? (
        <ErrorState error={rowError} retry={retryRows} />
      ) : rowPending ? (
        <LoadingState />
      ) : rows?.rows.length ? (
        <div className="leader-advanced-rows">
          {rows.rows.slice(0, 20).map((row, index) => (
            <div key={index} className="leader-advanced-row">
              <strong>
                {template === "change-routes"
                  ? `${display(row.Node)} · ${display(row.Network ?? row.Prefix)}`
                  : `${display(row.Flow ?? row.Start_Location)} → ${display(row.Destination ?? row.Destination_IP)}`}
              </strong>
              <Tag>
                {label[String(row.Change ?? "")] ?? display(row.Change)}
              </Tag>
            </div>
          ))}
        </div>
      ) : (
        <Empty description="所选范围没有返回变化记录；不能据此断言范围外无变化" />
      )}
      {(result.truncated || (total != null && total > 200)) && (
        <Alert
          type="warning"
          title="证据分页或截断，当前列表不能代表完整影响范围。"
        />
      )}
    </Card>
  );
}
