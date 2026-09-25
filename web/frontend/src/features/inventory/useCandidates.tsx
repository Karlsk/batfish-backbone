import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { Alert, Button, Space } from "antd";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "../../api/client";
import { resourceKey } from "../../app/context";
import { useSession } from "../../app/session";
import { ErrorState } from "../../components/States";
import { pollInterval } from "../jobs/model";
export function useCandidates(networkId: string, snapshotId: string) {
  const session = useSession();
  const context = { networkId, snapshotId };
  const [jobId, setJobId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const flight = useRef(false),
    alive = useRef(true);
  const key = useRef(crypto.randomUUID());
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const job = useQuery({
    queryKey: resourceKey(session?.user_id ?? null, context, "candidate-job", {
      jobId,
    }),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          signal,
          params: { path: { job_id: jobId! } },
        }),
      ),
    enabled: !!jobId,
    refetchInterval: (q) => pollInterval(q.state.data),
    refetchOnWindowFocus: "always",
  });
  const resultId = job.data?.result_id;
  const rows = useInfiniteQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "candidate-rows",
      {},
      resultId,
    ),
    queryFn: ({ signal, pageParam }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/rows", {
          signal,
          params: {
            path: { result_id: resultId! },
            query: { offset: pageParam, limit: 200 },
          },
        }),
      ),
    enabled: !!resultId,
    initialPageParam: 0,
    getNextPageParam: (last) =>
      last.offset + last.limit < last.total
        ? last.offset + last.limit
        : undefined,
  });
  async function load() {
    if (flight.current) return;
    flight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const data = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/nodes",
          {
            params: {
              path: { network_id: networkId, snapshot_id: snapshotId },
              header: { "idempotency-key": key.current },
            },
            body: {
              options: { properties: ["Hostname", "Interfaces", "VRFs"] },
            },
          },
        ),
      );
      if (alive.current) setJobId(data.id);
    } catch (e) {
      if (alive.current) setError(e);
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  const records = rows.data?.pages.flatMap((p) => p.rows) ?? [];
  const strings = (value: unknown): string[] =>
    Array.isArray(value)
      ? value.filter((v): v is string => typeof v === "string")
      : [];
  const name = (row: Record<string, unknown>) =>
    typeof row.Hostname === "string"
      ? row.Hostname
      : row.Node && typeof row.Node === "object" && "name" in row.Node
        ? String(row.Node.name)
        : "";
  const distinct = (values: string[]) => [...new Set(values)].sort();
  const terminalError = job.data?.error
    ? new ApiError(
        job.data.error.code,
        job.data.error.request_id,
        job.data.error.field_errors,
      )
    : undefined;
  const pending =
    busy ||
    (!!jobId &&
      (!job.data || ["queued", "running"].includes(job.data.status))) ||
    (!!resultId && rows.isPending);
  return {
    nodes: distinct(records.map(name).filter(Boolean)),
    interfaces: (names: string[]) =>
      distinct(
        records
          .filter((r) => !names.length || names.includes(name(r)))
          .flatMap((r) => strings(r.Interfaces)),
      ),
    vrfs: (names: string[]) =>
      distinct(
        records
          .filter((r) => !names.length || names.includes(name(r)))
          .flatMap((r) => strings(r.VRFs)),
      ),
    controls: (
      <div className="candidate-controls">
        <Space wrap>
          <Button
            loading={pending}
            disabled={!!jobId}
            onClick={() => void load()}
          >
            加载设备与接口候选
          </Button>
          {jobId && <Link to={`/jobs/${jobId}`}>候选查询任务</Link>}
          {records.length > 0 && (
            <span>已加载 {records.length} 台设备的候选值</span>
          )}
          {rows.hasNextPage && (
            <Button
              loading={rows.isFetchingNextPage}
              onClick={() => void rows.fetchNextPage()}
            >
              加载更多候选
            </Button>
          )}
        </Space>
        {pending && (
          <p className="muted">
            正在通过当前快照查询候选信息，请等待后台任务完成。
          </p>
        )}
        {error || job.error || rows.error || terminalError ? (
          <ErrorState
            error={error || job.error || rows.error || terminalError}
            retry={
              error
                ? () => void load()
                : rows.error
                  ? () => void rows.refetch()
                  : job.error
                    ? () => void job.refetch()
                    : undefined
            }
          />
        ) : null}
        {rows.data?.pages.some((p) => p.truncated) && (
          <Alert
            type="warning"
            title="候选结果已截断；可输入完整名称或使用专家表达式。"
          />
        )}
        {job.data?.status === "succeeded" &&
          rows.isSuccess &&
          !records.length && (
            <Alert
              type="info"
              title="当前快照没有设备候选；可查看诊断或输入已知名称。"
            />
          )}
        {job.data && ["cancelled", "interrupted"].includes(job.data.status) && (
          <Alert
            type="warning"
            title="候选查询被取消或中断，请在任务中心查看状态。"
          />
        )}
      </div>
    ),
  };
}
