import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, unwrap } from "../../../api/client";
import { resourceKey } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ErrorState, LoadingState } from "../../../components/States";
import { DetailsDrawer } from "../../../components/DetailsDrawer";
import { SourceDrawer, sourceTarget, type SourceTarget } from "./Source";
import type { components } from "../../../api/schema";
import { snapshotLabels } from "../model";
type Diagnostic = components["schemas"]["Diagnostic"];
const sourceLabels: Record<string, string> = {
  fileParseStatus: "文件解析状态",
  initIssues: "初始化问题",
  parseWarning: "解析警告",
  viConversionWarning: "模型转换警告",
};
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function QualitySummary({
  snapshot,
}: {
  snapshot: components["schemas"]["SnapshotDTO"];
}) {
  const q = snapshot.quality_summary;
  const limits = Array.isArray(q.model_limits) ? q.model_limits : [];
  const descriptions = [
    ...new Set(
      limits
        .map((item) => record(item).description)
        .filter((text): text is string => typeof text === "string"),
    ),
  ];
  return (
    <Card title="解析与模型覆盖">
      <Space wrap>
        <Tag color={snapshot.status === "failed" ? "red" : "blue"}>
          {snapshotLabels[snapshot.status]}
        </Tag>
        <span>文件 {String(q.file_count ?? "尚未统计")}</span>
        <span>设备 {String(q.node_count ?? "尚未统计")}</span>
        <span>初始化问题 {String(q.issue_count ?? "尚未统计")}</span>
      </Space>
      <Alert
        type="warning"
        showIcon
        title={
          q.coverage === "limited"
            ? "模型覆盖有限"
            : q.coverage === "complete"
              ? "仅对已声明支持的能力给出结论"
              : "模型覆盖范围未完整确认"
        }
        description="解析完成不等于全部网络能力已被模拟；请结合下方诊断和模型限制判断。"
      />
      {descriptions.map((description) => (
        <Alert key={description} type="warning" showIcon title={description} />
      ))}
      <p className="record-id">
        来源快照：{snapshot.id} · 引擎 {snapshot.engine_version ?? "尚未记录"} ·
        SDK {snapshot.sdk_version ?? "尚未记录"}
      </p>
    </Card>
  );
}
export function DiagnosticsPage() {
  const { networkId, snapshotId } = useParams();
  return (
    <DiagnosticsView
      key={`${networkId}:${snapshotId}`}
      networkId={networkId!}
      snapshotId={snapshotId!}
    />
  );
}
function DiagnosticsView({
  networkId,
  snapshotId,
}: {
  networkId: string;
  snapshotId: string;
}) {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const [severity, setSeverity] = useState<
    "info" | "warning" | "error" | undefined
  >();
  const [target, setTarget] = useState<SourceTarget | null>(null);
  const [raw, setRaw] = useState<Diagnostic | null>(null);
  const context = { networkId, snapshotId };
  const snapshot = useQuery({
    queryKey: resourceKey(session?.user_id ?? null, context, "snapshot"),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: { path: { network_id: networkId, snapshot_id: snapshotId } },
        }),
      ),
    refetchInterval: (q) =>
      ["queued", "initializing"].includes(q.state.data?.status ?? "")
        ? 2000
        : false,
  });
  const waiting = ["queued", "initializing"].includes(
    snapshot.data?.status ?? "",
  );
  const diagnostics = useQuery({
    queryKey: resourceKey(session?.user_id ?? null, context, "diagnostics", {
      offset,
      severity,
      limit: 20,
    }),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/diagnostics",
          {
            signal,
            params: {
              path: { network_id: networkId, snapshot_id: snapshotId },
              query: { offset, limit: 20, severity },
            },
          },
        ),
      ),
    enabled: !!snapshot.data && !waiting,
    retry: false,
  });
  const files = useQuery({
    queryKey: resourceKey(session?.user_id ?? null, context, "snapshot-files"),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}/files", {
          signal,
          params: { path: { network_id: networkId, snapshot_id: snapshotId } },
        }),
      ),
    enabled: !!snapshot.data,
  });
  if (snapshot.isPending) return <LoadingState />;
  if (snapshot.isError) return <ErrorState error={snapshot.error} />;
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>
            {snapshot.data.display_name} · 解析诊断
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            查看模型覆盖、配置问题和对应文件证据。
          </Typography.Paragraph>
        </div>
        {snapshot.data.initialization_job_id && (
          <Link to={`/jobs/${snapshot.data.initialization_job_id}`}>
            <Button>初始化任务</Button>
          </Link>
        )}
      </div>
      <QualitySummary snapshot={snapshot.data} />
      <Card title="解析诊断" className="diagnostic-card">
        <Select
          aria-label="诊断级别"
          placeholder="全部级别"
          allowClear
          value={severity}
          virtual={false}
          style={{ width: 180, marginBottom: 16 }}
          options={[
            { value: "info", label: "信息" },
            { value: "warning", label: "警告" },
            { value: "error", label: "错误" },
          ]}
          onChange={(value) => {
            setSeverity(value);
            setOffset(0);
          }}
        />
        {waiting ? (
          <Alert type="info" title="初始化尚未完成，诊断将在任务完成后显示。" />
        ) : diagnostics.isError ? (
          <ErrorState
            error={diagnostics.error}
            retry={() => void diagnostics.refetch()}
          />
        ) : (
          <Table<Diagnostic>
            rowKey={(d) =>
              JSON.stringify([
                d.source,
                d.severity,
                d.description,
                d.locations,
                d.raw,
              ])
            }
            loading={diagnostics.isPending}
            dataSource={diagnostics.data?.items}
            pagination={{
              current: offset / 20 + 1,
              pageSize: 20,
              total: diagnostics.data?.total,
              showSizeChanger: false,
              onChange: (page) => setOffset((page - 1) * 20),
            }}
            columns={[
              {
                title: "级别",
                dataIndex: "severity",
                render: (value) => (
                  <Tag
                    color={
                      value === "error"
                        ? "red"
                        : value === "warning"
                          ? "orange"
                          : "blue"
                    }
                  >
                    {
                      { info: "信息", warning: "警告", error: "错误" }[
                        value as "info"
                      ]
                    }
                  </Tag>
                ),
              },
              {
                title: "来源",
                dataIndex: "source",
                render: (value) => sourceLabels[value] ?? value,
              },
              {
                title: "说明",
                dataIndex: "description",
                render: (value) => (
                  <span className="diagnostic-description">{value}</span>
                ),
              },
              {
                title: "配置位置",
                render: (_, d) =>
                  d.locations.length ? (
                    <Space orientation="vertical">
                      {d.locations.map((location, index) => {
                        const known = sourceTarget(location);
                        return known ? (
                          <Button
                            key={index}
                            type="link"
                            onClick={() => setTarget(known)}
                          >
                            {location.path}
                            {known.lines.length
                              ? `：${known.lines.join(", ")}`
                              : "（未提供行号）"}
                          </Button>
                        ) : (
                          <span key={index}>
                            {location.path}（文件位置不可用）
                          </span>
                        );
                      })}
                    </Space>
                  ) : (
                    <span>未提供文件位置</span>
                  ),
              },
              {
                title: "详情",
                render: (_, d) => (
                  <Button type="link" onClick={() => setRaw(d)}>
                    原始说明
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
      <Card title="快照原始文件">
        {files.isError ? (
          <ErrorState error={files.error} />
        ) : (
          <Table
            rowKey="id"
            loading={files.isPending}
            dataSource={files.data?.items}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            columns={[
              { title: "文件路径", dataIndex: "path" },
              { title: "编码", dataIndex: "encoding" },
              {
                title: "行数",
                dataIndex: "line_count",
                render: (value) => value ?? "未知",
              },
              {
                title: "操作",
                render: (_, file) => (
                  <Button
                    type="link"
                    onClick={() =>
                      setTarget({
                        fileId: file.id,
                        path: file.path,
                        lines: [],
                        offset: 0,
                      })
                    }
                  >
                    查看文件
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
      <SourceDrawer
        networkId={networkId}
        snapshotId={snapshotId}
        target={target}
        onClose={() => setTarget(null)}
      />
      <DetailsDrawer
        open={!!raw}
        title="原始诊断说明"
        onClose={() => setRaw(null)}
        queryKey={resourceKey(
          session?.user_id ?? null,
          context,
          "diagnostic-raw",
          { raw },
        )}
        load={async () => raw?.raw}
      />
    </>
  );
}
