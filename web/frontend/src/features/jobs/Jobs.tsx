import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, unwrap, ApiError } from "../../api/client";
import { useSession } from "../../app/session";
import { useResourceContext, resourceKey } from "../../app/context";
import { ErrorState, LoadingState } from "../../components/States";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import {
  durationLabel,
  canCancel,
  canRetry,
  jobLabels,
  kindLabels,
  phaseLabels,
  pollInterval,
  type Job,
} from "./model";
export function JobsPage() {
  const session = useSession();
  const { network } = useResourceContext();
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<Job["status"] | undefined>();
  const [mine, setMine] = useState(false);
  const [currentNetwork, setCurrentNetwork] = useState(false);
  const networkId = currentNetwork ? network?.id : undefined;
  const params = {
    offset,
    limit: 20,
    status,
    network_id: networkId,
    created_by: mine ? session?.user_id : undefined,
  };
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: networkId ?? null, snapshotId: null },
      "jobs",
      params,
    ),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/jobs", { signal, params: { query: params } })),
    refetchInterval: 5000,
    refetchOnWindowFocus: "always",
  });
  useEffect(() => setOffset(0), [networkId]);
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>任务中心</Typography.Title>
          <Typography.Paragraph type="secondary">
            共享任务历史。离开页面不会取消后台执行。
          </Typography.Paragraph>
        </div>
        <Button onClick={() => void query.refetch()}>刷新</Button>
      </div>
      <Space wrap className="filter-bar">
        <Select
          aria-label="任务状态"
          placeholder="全部状态"
          allowClear
          style={{ width: 170 }}
          value={status}
          virtual={false}
          options={Object.entries(jobLabels).map(([value, label]) => ({
            value,
            label,
          }))}
          onChange={(value) => {
            setStatus(value);
            setOffset(0);
          }}
        />
        <Checkbox
          checked={mine}
          onChange={(e) => {
            setMine(e.target.checked);
            setOffset(0);
          }}
        >
          仅我发起
        </Checkbox>
        <Checkbox
          checked={currentNetwork}
          disabled={!network}
          onChange={(e) => {
            setCurrentNetwork(e.target.checked);
            setOffset(0);
          }}
        >
          仅当前网络
        </Checkbox>
      </Space>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <Card>
          <Table<Job>
            rowKey="id"
            loading={query.isPending}
            dataSource={query.data?.items}
            pagination={{
              current: offset / 20 + 1,
              pageSize: 20,
              total: query.data?.total,
              showSizeChanger: false,
              onChange: (page) => setOffset((page - 1) * 20),
            }}
            columns={[
              {
                title: "任务",
                render: (_, j) => (
                  <Link to={`/jobs/${j.id}`}>
                    {kindLabels[j.kind]} · {j.id.slice(0, 8)}
                  </Link>
                ),
              },
              {
                title: "状态",
                render: (_, j) => <Tag>{jobLabels[j.status]}</Tag>,
              },
              {
                title: "阶段",
                render: (_, j) => phaseLabels[j.phase] ?? "处理中",
              },
              {
                title: "来源网络",
                render: (_, j) => (
                  <span title={j.resource_ids.network_id}>
                    {j.resource_ids.network_id?.slice(0, 8) ?? "—"}
                  </span>
                ),
              },
              {
                title: "发起人",
                render: (_, j) => (
                  <span title={j.created_by}>{j.created_by.slice(0, 8)}</span>
                ),
              },
              { title: "执行耗时", render: (_, j) => durationLabel(j) },
              {
                title: "创建时间",
                render: (_, j) =>
                  new Date(j.created_at).toLocaleString("zh-CN"),
              },
            ]}
          />
        </Card>
      )}
    </>
  );
}
export function JobDetail() {
  const { jobId } = useParams();
  return <JobView key={jobId} jobId={jobId!} />;
}
function JobView({ jobId }: { jobId: string }) {
  const session = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [details, setDetails] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [action, setAction] = useState<"cancel" | "retry">();
  const requestKey = useMemo(() => crypto.randomUUID(), [jobId]);
  const inFlight = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const key = resourceKey(
    session?.user_id ?? null,
    { networkId: null, snapshotId: null },
    "job",
    { jobId },
  );
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          signal,
          params: { path: { job_id: jobId } },
        }),
      ),
    refetchInterval: (query) => pollInterval(query.state.data),
    refetchOnWindowFocus: "always",
  });
  const job = query.data;
  const original = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: null, snapshotId: null },
      "job",
      { jobId: job?.retry_of },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          signal,
          params: { path: { job_id: job!.retry_of! } },
        }),
      ),
    enabled: !!job?.retry_of,
  });
  async function mutate(operation: "cancel" | "retry") {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    setAction(operation);
    try {
      const result =
        operation === "cancel"
          ? await unwrap(
              api.POST("/api/v1/jobs/{job_id}/cancel", {
                params: { path: { job_id: jobId } },
              }),
            )
          : await unwrap(
              api.POST("/api/v1/jobs/{job_id}/retry", {
                params: {
                  path: { job_id: jobId },
                  header: { "idempotency-key": requestKey },
                },
              }),
            );
      await client.invalidateQueries({
        predicate: (q) =>
          ["job", "jobs", "snapshots"].includes(String(q.queryKey[5])),
      });
      if (alive.current) {
        if (operation === "retry") navigate(`/jobs/${result.id}`);
        else client.setQueryData(key, result);
      }
    } catch (e) {
      if (alive.current) {
        setError(e);
        void query.refetch();
      }
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  if (query.isPending) return <LoadingState />;
  if (query.isError)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  if (!job) return null;
  const networkId = job.resource_ids.network_id;
  const snapshotId = job.resource_ids.snapshot_id;
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>
            {kindLabels[job.kind]}任务
          </Typography.Title>
          <span className="record-id">{job.id}</span>
        </div>
        <Link to="/jobs">
          <Button>全部任务</Button>
        </Link>
      </div>
      <Card>
        <Space wrap>
          <Tag
            color={
              job.status === "succeeded"
                ? "green"
                : ["failed", "interrupted"].includes(job.status)
                  ? "red"
                  : "blue"
            }
          >
            {jobLabels[job.status]}
          </Tag>
          <span>{phaseLabels[job.phase] ?? "处理中"}</span>
          <span>第 {job.attempt} 次执行</span>
          <span>执行耗时：{durationLabel(job)}</span>
        </Space>
        {job.status === "interrupted" || job.engine_state === "unknown" ? (
          <Alert
            type="warning"
            showIcon
            title="执行中断时引擎状态可能未知"
            description="请管理员核对当前引擎是否已停止并完成对账；客户端超时不表示引擎停止。服务端会阻止未对账的重试。"
          />
        ) : null}
        {job.status === "running" && (
          <p className="muted">
            任务已经开始，暂不支持取消。离开页面不会终止执行。
          </p>
        )}
        {!!error &&
          (error instanceof ApiError && error.code === "CONFLICT" ? (
            <Alert
              type="warning"
              showIcon
              title={
                action === "cancel"
                  ? "任务可能已被领取，无法取消排队；已刷新当前状态。"
                  : "当前状态不能重试，请检查引擎与快照状态。"
              }
            />
          ) : (
            <ErrorState error={error} />
          ))}
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
        <Descriptions
          column={1}
          items={[
            {
              key: "network",
              label: "来源网络",
              children: networkId ?? "未记录",
            },
            {
              key: "snapshot",
              label: "来源快照",
              children: snapshotId ?? "未记录",
            },
            { key: "owner", label: "发起人", children: job.created_by },
            {
              key: "created",
              label: "创建时间",
              children: new Date(job.created_at).toLocaleString("zh-CN"),
            },
          ]}
        />
        {job.retry_of && (
          <Alert
            type="info"
            showIcon
            title={
              job.kind === "initialization"
                ? "这是一个新建的重试任务，旧快照状态保持不变"
                : "这是一个新建的重试任务，沿用原快照"
            }
            description={
              <>
                <Link to={`/jobs/${job.retry_of}`}>查看旧任务</Link>
                {job.kind === "initialization" ? (
                  <>
                    <p>
                      旧快照：
                      {original.data?.resource_ids.snapshot_id ?? "读取中"}
                    </p>
                    <p>新快照：{snapshotId}</p>
                  </>
                ) : (
                  <p>沿用快照：{snapshotId ?? "未记录"}</p>
                )}
                {original.isError && <ErrorState error={original.error} />}
              </>
            }
          />
        )}
        <Space wrap className="action-bar">
          {canCancel(job, session) && (
            <Button danger loading={busy} onClick={() => void mutate("cancel")}>
              取消排队
            </Button>
          )}
          {canRetry(job, session) && (
            <Button
              type="primary"
              loading={busy}
              onClick={() => void mutate("retry")}
            >
              新建重试任务
            </Button>
          )}
          <Button onClick={() => setDetails(true)}>查看参数与来源详情</Button>
          {networkId && snapshotId && (
            <Link
              to={`/networks/${networkId}/snapshots/${snapshotId}/diagnostics`}
            >
              <Button>查看解析诊断</Button>
            </Link>
          )}
          <Link to="/snapshots">
            <Button>返回快照列表</Button>
          </Link>
        </Space>
      </Card>
      <DetailsDrawer
        open={details}
        title="任务参数与来源"
        onClose={() => setDetails(false)}
        queryKey={resourceKey(
          session?.user_id ?? null,
          { networkId: networkId ?? null, snapshotId: snapshotId ?? null },
          "job-parameters",
          { jobId },
        )}
        load={async () => ({
          requested_parameters: job.requested_parameters,
          effective_parameters: job.effective_parameters,
          context: job.context,
          phase: job.phase,
        })}
      />
    </>
  );
}
