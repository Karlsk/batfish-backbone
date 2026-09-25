import { DeleteResource } from "./DeleteResource";
import { Button, Card, Space, Table, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import { useResourceContext } from "../../app/context";
import { useSnapshots } from "../networks/queries";
import { EmptyState, ErrorState } from "../../components/States";
import { UploadWizard } from "./UploadWizard";
import type { components } from "../../api/schema";
import { snapshotLabels } from "./model";
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
                      <Link
                        to={`/networks/${network.id}/snapshots/${s.id}/diagnostics`}
                      >
                        诊断
                      </Link>
                      <Button
                        disabled={["deleting", "deleted"].includes(s.status)}
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
                      <DeleteResource
                        key={s.id}
                        networkId={network.id}
                        snapshotId={s.id}
                        name={s.display_name}
                        state={s.status}
                        jobId={s.deletion_job_id}
                      />
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
