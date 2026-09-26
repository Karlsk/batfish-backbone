import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Radio,
  Select,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, ApiError, unwrap } from "../../api/client";
import { resourceKey, useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { EmptyState, ErrorState } from "../../components/States";
import { useDraftGuard } from "../../components/useDraftGuard";
import { traceProtocols } from "../inventory/catalog";
import { useCandidates } from "../inventory/useCandidates";
import { pollInterval } from "../jobs/model";
import {
  buildFilterTest,
  defaultFilterDraft,
  type FilterDraft,
} from "./requests";

type Request = components["schemas"]["FilterTestRequest"];

export function isUnsupportedAcl(error: unknown) {
  return (
    error instanceof ApiError &&
    error.code === "CONFLICT" &&
    error.fieldErrors.some((field) =>
      field.message.includes("ACL verification is unsupported"),
    )
  );
}

export function FilterTestPage() {
  const { network, snapshot } = useResourceContext();
  return (
    <>
      <Typography.Title level={2}>ACL 流量测试</Typography.Title>
      {network && snapshot ? (
        <FilterTestForm
          key={`${network.id}:${snapshot.id}`}
          networkId={network.id}
          snapshotId={snapshot.id}
        />
      ) : (
        <EmptyState
          title="请先选择网络与就绪快照"
          action={
            <Link to="/snapshots">
              <Button>选择快照</Button>
            </Link>
          }
        />
      )}
    </>
  );
}

export function FilterTestForm({
  networkId,
  snapshotId,
}: {
  networkId: string;
  snapshotId: string;
}) {
  const navigate = useNavigate();
  const session = useSession();
  const candidates = useCandidates(networkId, snapshotId);
  const [draft, setDraft] = useState(defaultFilterDraft);
  const [resolverJobId, setResolverJobId] = useState<string>();
  const [resolverError, setResolverError] = useState<unknown>();
  const [loadingFilters, setLoadingFilters] = useState(false);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<unknown>();
  const [validation, setValidation] = useState("");
  const alive = useRef(true);
  const flight = useRef(false);
  const filterFlight = useRef(false);
  const currentNode = useRef("");
  const resolverAttempt = useRef<{ key: string; node: string } | null>(null);
  const attempt = useRef<{ key: string; body: Request } | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const guard = useDraftGuard(
    locked || JSON.stringify(draft) !== JSON.stringify(defaultFilterDraft()),
    busy,
  );
  const context = { networkId, snapshotId };
  const resolverJob = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "acl-candidate-job",
      { resolverJobId },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          signal,
          params: { path: { job_id: resolverJobId! } },
        }),
      ),
    enabled: !!resolverJobId,
    refetchInterval: (query) => pollInterval(query.state.data),
    refetchOnWindowFocus: "always",
  });
  const resultId = resolverJob.data?.result_id;
  const filters = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "acl-candidate-rows",
      { node: draft.node },
      resultId,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/rows", {
          signal,
          params: {
            path: { result_id: resultId! },
            query: { offset: 0, limit: 200 },
          },
        }),
      ),
    enabled:
      !!resultId &&
      !!draft.node &&
      resolverAttempt.current?.node === draft.node,
  });
  const available = [
    ...new Set(
      (filters.data?.rows ?? [])
        .map((row) => row.Filter_Name)
        .filter((name): name is string => typeof name === "string"),
    ),
  ].sort();
  const update = <K extends keyof FilterDraft>(key: K, value: FilterDraft[K]) =>
    setDraft((old) => ({ ...old, [key]: value }));
  function chooseNode(node: string) {
    currentNode.current = node;
    setDraft((old) => ({ ...old, node, filter: "" }));
    setResolverJobId(undefined);
    setResolverError(undefined);
    resolverAttempt.current = null;
  }
  async function loadFilters() {
    if (filterFlight.current || !draft.node.trim()) return;
    filterFlight.current = true;
    setLoadingFilters(true);
    setResolverError(undefined);
    resolverAttempt.current ??= { key: crypto.randomUUID(), node: draft.node };
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/resolve-filters",
          {
            params: {
              path: { network_id: networkId, snapshot_id: snapshotId },
              header: { "idempotency-key": resolverAttempt.current.key },
            },
            body: {
              nodes: {
                mode: "literal",
                values: [resolverAttempt.current.node],
              },
            },
          },
        ),
      );
      if (
        alive.current &&
        currentNode.current === resolverAttempt.current?.node
      )
        setResolverJobId(job.id);
    } catch (caught) {
      if (alive.current) {
        setResolverError(caught);
        if (
          caught instanceof ApiError &&
          [
            "VALIDATION_ERROR",
            "FORBIDDEN",
            "NOT_READY",
            "RATE_LIMITED",
            "NOT_FOUND",
            "CONFLICT",
          ].includes(caught.code)
        )
          resolverAttempt.current = null;
      }
    } finally {
      filterFlight.current = false;
      if (alive.current) setLoadingFilters(false);
    }
  }
  async function submit() {
    if (flight.current) return;
    setValidation("");
    let body: Request;
    try {
      body = buildFilterTest(draft);
    } catch (caught) {
      setValidation((caught as Error).message);
      return;
    }
    attempt.current ??= { key: crypto.randomUUID(), body };
    flight.current = true;
    setBusy(true);
    setLocked(true);
    setError(undefined);
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/test-filters",
          {
            params: {
              path: { network_id: networkId, snapshot_id: snapshotId },
              header: { "idempotency-key": attempt.current.key },
            },
            body: attempt.current.body,
          },
        ),
      );
      if (alive.current) {
        guard.allowNavigation();
        navigate(`/jobs/${job.id}`);
      }
    } catch (caught) {
      if (alive.current) {
        setError(caught);
        if (
          caught instanceof ApiError &&
          [
            "VALIDATION_ERROR",
            "FORBIDDEN",
            "NOT_READY",
            "RATE_LIMITED",
            "NOT_FOUND",
            "CONFLICT",
          ].includes(caught.code)
        ) {
          attempt.current = null;
          setLocked(false);
        }
      }
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  const advancedCount =
    Number(draft.nodeMode === "expression") +
    Number(draft.filterMode === "expression") +
    Number(draft.protocols.join(",") !== "icmp") +
    Number(!!draft.sourcePorts) +
    Number(!!draft.destinationPorts);
  return (
    <Card title="指定设备、ACL 与流量">
      {guard.holder}
      <Alert
        type="info"
        title="结果仅判断所选 ACL 对这条流量的局部动作，不代表端到端可达。"
      />
      {candidates.controls}
      {resolverError != null && (
        <ErrorState error={resolverError} retry={() => void loadFilters()} />
      )}
      {resolverJob.isError && (
        <ErrorState
          error={resolverJob.error}
          retry={() => void resolverJob.refetch()}
        />
      )}
      {resolverJob.data?.error && (
        <Alert type="error" title="ACL 候选查询失败，请查看任务中心。" />
      )}
      {filters.isError && (
        <ErrorState
          error={filters.error}
          retry={() => void filters.refetch()}
        />
      )}
      {filters.data?.truncated && (
        <Alert type="warning" title="ACL 候选已截断；专家可输入表达式。" />
      )}
      {resolverJob.data?.status === "succeeded" &&
        filters.isSuccess &&
        !available.length && (
          <Alert
            type="warning"
            title="此设备没有已解析的 ACL；不能据此判断放行。"
          />
        )}
      {error != null &&
        (isUnsupportedAcl(error) ? (
          <Alert
            type="warning"
            title="当前快照的 ACL 模型暂不支持验证；不能给出放行结论。"
          />
        ) : (
          <ErrorState error={error} />
        ))}
      {validation && <Alert type="error" title={validation} />}
      {locked && !busy && error != null && (
        <Alert
          type="info"
          title="提交结果尚未确认；重试保留原参数和请求标识。"
        />
      )}
      <Form layout="vertical" disabled={busy || locked}>
        {draft.nodeMode === "literal" && (
          <Form.Item label="设备">
            <Select
              aria-label="设备"
              showSearch
              virtual={false}
              value={draft.node || undefined}
              options={candidates.nodes.map((value) => ({
                value,
                label: value,
              }))}
              placeholder="先加载设备候选"
              onChange={chooseNode}
            />
          </Form.Item>
        )}
        {draft.nodeMode === "literal" && (
          <Button
            className="action-bar"
            loading={
              loadingFilters || resolverJob.isFetching || filters.isFetching
            }
            disabled={!draft.node}
            onClick={() => void loadFilters()}
          >
            加载此设备 ACL
          </Button>
        )}
        {draft.filterMode === "literal" && (
          <Form.Item label="ACL">
            <Select
              aria-label="ACL"
              showSearch
              virtual={false}
              value={draft.filter || undefined}
              options={available.map((value) => ({ value, label: value }))}
              placeholder="先加载当前设备的 ACL"
              onChange={(value) => update("filter", value)}
            />
          </Form.Item>
        )}
        <Form.Item label="源 IPv4 地址">
          <Input
            aria-label="源 IPv4 地址"
            value={draft.source}
            onChange={(event) => update("source", event.target.value)}
            placeholder="如 10.64.0.1"
          />
        </Form.Item>
        <Form.Item label="目标 IPv4 地址">
          <Input
            aria-label="目标 IPv4 地址"
            value={draft.destination}
            onChange={(event) => update("destination", event.target.value)}
            placeholder="如 10.64.0.2"
          />
        </Form.Item>
        <AdvancedOptions activeCount={advancedCount}>
          <Form.Item label="设备选择方式">
            <Radio.Group
              aria-label="设备选择方式"
              value={draft.nodeMode}
              onChange={(event) => update("nodeMode", event.target.value)}
              options={[
                { label: "候选设备", value: "literal" },
                { label: "专家表达式", value: "expression" },
              ]}
            />
          </Form.Item>
          {draft.nodeMode === "expression" && (
            <Form.Item label="设备表达式">
              <Input
                aria-label="设备表达式"
                value={draft.nodeExpression}
                onChange={(event) =>
                  update("nodeExpression", event.target.value)
                }
              />
            </Form.Item>
          )}
          <Form.Item label="ACL 选择方式">
            <Radio.Group
              aria-label="ACL 选择方式"
              value={draft.filterMode}
              onChange={(event) => update("filterMode", event.target.value)}
              options={[
                { label: "已解析 ACL", value: "literal" },
                { label: "专家表达式", value: "expression" },
              ]}
            />
          </Form.Item>
          {draft.filterMode === "expression" && (
            <Form.Item label="ACL 表达式">
              <Input
                aria-label="ACL 表达式"
                value={draft.filterExpression}
                onChange={(event) =>
                  update("filterExpression", event.target.value)
                }
              />
            </Form.Item>
          )}
          <Form.Item label="IP 协议">
            <Select
              aria-label="IP 协议"
              mode="multiple"
              virtual={false}
              value={draft.protocols}
              options={traceProtocols.map((value) => ({
                value,
                label: value.toUpperCase(),
              }))}
              onChange={(value) => update("protocols", value)}
            />
          </Form.Item>
          <Form.Item label="源端口（可选）">
            <Input
              aria-label="源端口"
              value={draft.sourcePorts}
              onChange={(event) => update("sourcePorts", event.target.value)}
              placeholder="TCP/UDP端口，逗号分隔"
            />
          </Form.Item>
          <Form.Item label="目标端口（可选）">
            <Input
              aria-label="目标端口"
              value={draft.destinationPorts}
              onChange={(event) =>
                update("destinationPorts", event.target.value)
              }
              placeholder="TCP/UDP端口，逗号分隔"
            />
          </Form.Item>
        </AdvancedOptions>
      </Form>
      <Button
        type="primary"
        className="action-bar"
        loading={busy}
        onClick={() => void submit()}
      >
        {locked ? "重试 ACL 提交" : "测试 ACL 流量"}
      </Button>
    </Card>
  );
}
