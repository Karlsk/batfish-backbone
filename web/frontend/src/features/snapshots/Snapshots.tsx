import { Button, Card, Space, Table, Tag, Typography } from "antd";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap, ApiError } from "../../api/client";
import { useResourceContext, resourceKey } from "../../app/context";
import { useSession } from "../../app/session";
import { useSnapshots } from "../networks/queries";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { UploadWizard } from "./UploadWizard";
import type { components } from "../../api/schema";
export const snapshotLabels: Record<string, string> = {
  queued: "排队中",
  initializing: "初始化中",
  ready: "就绪",
  ready_with_warnings: "就绪（有警告）",
  failed: "初始化失败",
  deleting: "删除中",
  deleted: "已删除",
};
export const jobLabels: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "执行中断",
};
export function SnapshotsPage() {
  const { network, snapshot, selectSnapshot } = useResourceContext();
  const query = useSnapshots(network?.id ?? null);
  if (!network)
    return (
      <EmptyState
        title="请先选择一个网络"
        action={
          <Link to="/networks">
            <Button type="primary">查看或创建网络</Button>
          </Link>
        }
      />
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>{network.name}</Typography.Title>
          <Typography.Paragraph type="secondary">
            快照保留导入时的配置，不覆盖历史快照。
          </Typography.Paragraph>
        </div>
        <Link to="/networks">
          <Button>返回网络列表</Button>
        </Link>
      </div>
      <UploadWizard key={network.id} network={network} />
      <Card title="快照记录">
        {query.isError ? (
          <ErrorState error={query.error} retry={() => void query.refetch()} />
        ) : (
          <>
            <Table<components["schemas"]["SnapshotDTO"]>
              rowKey="id"
              loading={query.isPending}
              dataSource={query.data?.pages.flatMap((page) => page.items)}
              pagination={false}
              locale={{ emptyText: "暂无快照，请先上传配置。" }}
              columns={[
                {
                  title: "快照名称",
                  render: (_, s) => (
                    <>
                      <strong>{s.display_name}</strong>
                      <div className="record-id">{s.id}</div>
                    </>
                  ),
                },
                {
                  title: "状态",
                  render: (_, s) => (
                    <Tag
                      color={
                        s.status === "ready"
                          ? "green"
                          : s.status === "failed"
                            ? "red"
                            : "orange"
                      }
                    >
                      {snapshotLabels[s.status]}
                    </Tag>
                  ),
                },
                {
                  title: "发起人",
                  dataIndex: "created_by",
                  render: (v) => <span title={v}>{v.slice(0, 8)}</span>,
                },
                {
                  title: "创建时间",
                  dataIndex: "created_at",
                  render: (v) => new Date(v).toLocaleString("zh-CN"),
                },
                {
                  title: "操作",
                  render: (_, s) => (
                    <Space>
                      <Button
                        type="link"
                        onClick={() =>
                          void selectSnapshot({
                            id: s.id,
                            name: s.display_name,
                            networkId: network.id,
                          })
                        }
                      >
                        {snapshot?.id === s.id ? "当前快照" : "选择快照"}
                      </Button>
                      {s.initialization_job_id && (
                        <Link to={`/jobs/${s.initialization_job_id}`}>
                          任务
                        </Link>
                      )}
                    </Space>
                  ),
                },
              ]}
            />
            {query.hasNextPage && (
              <Button
                loading={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                加载更多快照
              </Button>
            )}
          </>
        )}
      </Card>
    </>
  );
}
export function InitializationJobPage() {
  const { jobId } = useParams();
  const session = useSession();
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: null, snapshotId: null },
      "job",
      { jobId },
    ),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          params: { path: { job_id: jobId! } },
        }),
      ),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "queued")
        ? 2000
        : false,
  });
  if (query.isPending) return <LoadingState />;
  if (query.isError)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const job = query.data;
  return (
    <Card title={job.kind === "initialization" ? "初始化任务" : "任务记录"}>
      <Tag>{jobLabels[job.status] ?? job.status}</Tag>
      <p>任务编号：{job.id}</p>
      <p className="record-id">
        来源网络：{job.resource_ids.network_id ?? "未记录"} · 来源快照：
        {job.resource_ids.snapshot_id ?? "未记录"}
      </p>
      <p>创建时间：{new Date(job.created_at).toLocaleString("zh-CN")}</p>
      {job.error && (
        <ErrorState
          error={
            new ApiError(
              job.error.code,
              job.error.request_id,
              job.error.field_errors,
            )
          }
        />
      )}
      <p>当前页面显示任务实际状态，初始化完成后再检查快照质量。</p>
      <Link to="/snapshots">
        <Button>返回快照列表</Button>
      </Link>
    </Card>
  );
}
