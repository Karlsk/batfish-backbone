import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { resourceKey, useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { ChangeResults } from "./ChangeResults";
import { useSnapshots } from "../networks/queries";

export { ChangeResults } from "./ChangeResults";
type Comparison = components["schemas"]["ComparisonDTO"];
type Snapshot = components["schemas"]["SnapshotDTO"];
type Kind = "config" | "routes" | "reachability";

const knownRejection = new Set([
  "VALIDATION_ERROR",
  "FORBIDDEN",
  "NOT_READY",
  "RATE_LIMITED",
  "NOT_FOUND",
  "CONFLICT",
]);
function editableSnapshot(snapshot: Snapshot) {
  return (
    snapshot.status === "ready" || snapshot.status === "ready_with_warnings"
  );
}

function AnalysisPane({
  comparison,
  kind,
}: {
  comparison: Comparison;
  kind: Kind;
}) {
  const session = useSession();
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [locked, setLocked] = useState(false);
  const attempt = useRef<{ key: string; body: unknown } | null>(null);
  const [node, setNode] = useState("");
  const [prefix, setPrefix] = useState("");
  const [destination, setDestination] = useState("");
  const [start, setStart] = useState("");
  const [source, setSource] = useState("");
  const [protocols, setProtocols] = useState<string[]>(["icmp"]);
  const [ports, setPorts] = useState("");
  const [maxTraces, setMaxTraces] = useState(5);
  const [validation, setValidation] = useState("");
  const context = {
    networkId: comparison.network_id,
    snapshotId: comparison.candidate_snapshot_id,
  };
  const job = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      `comparison-${comparison.id}-${kind}-job`,
      {},
      jobId,
    ),
    enabled: !!jobId,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          signal,
          params: { path: { job_id: jobId! } },
        }),
      ),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 2000
        : false,
  });
  const result = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      `comparison-${comparison.id}-${kind}-result`,
      {},
      job.data?.result_id ?? null,
    ),
    enabled: job.data?.status === "succeeded" && !!job.data.result_id,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}", {
          signal,
          params: { path: { result_id: job.data!.result_id! } },
        }),
      ),
  });
  async function submit() {
    if (busy || (locked && !attempt.current)) return;
    setValidation("");
    setError(undefined);
    if (kind === "reachability" && (!destination.trim() || !start.trim())) {
      setValidation("必须填写目的 IPv4 范围与起点设备或接口。");
      return;
    }
    if (kind === "reachability" && protocols.length === 0) {
      setValidation("请至少选择一种 IP 协议。");
      return;
    }
    const values = ports
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (
      kind === "reachability" &&
      values.some((value) => !/^\d+$/.test(value) || Number(value) > 65535)
    ) {
      setValidation("目标端口必须是 0～65535 的整数，用逗号分隔。");
      return;
    }
    if (
      kind === "reachability" &&
      values.length > 0 &&
      protocols.some((protocol) => !["tcp", "udp"].includes(protocol))
    ) {
      setValidation("目标端口仅适用于 TCP/UDP，请调整协议。");
      return;
    }
    const body =
      kind === "config"
        ? { options: {} }
        : kind === "routes"
          ? {
              ...(node.trim()
                ? { nodes: { mode: "expression", expression: node.trim() } }
                : {}),
              options: { ...(prefix.trim() ? { network: prefix.trim() } : {}) },
            }
          : {
              destination_ips: destination.trim(),
              start_location: start.trim(),
              options: {
                ...(source.trim() ? { source_ips: source.trim() } : {}),
                ip_protocols: protocols,
                ...(values.length
                  ? { destination_ports: values.map(Number) }
                  : {}),
                max_traces: maxTraces,
              },
            };
    attempt.current ??= { key: crypto.randomUUID(), body };
    setBusy(true);
    setLocked(true);
    const params = {
      path: { comparison_id: comparison.id },
      header: { "idempotency-key": attempt.current.key },
    };
    try {
      const frozen = attempt.current.body;
      const submitted =
        kind === "config"
          ? await unwrap(
              api.POST(
                "/api/v1/comparisons/{comparison_id}/analyses/config-diff",
                {
                  params,
                  body: frozen as components["schemas"]["ConfigDiffRequest"],
                },
              ),
            )
          : kind === "routes"
            ? await unwrap(
                api.POST(
                  "/api/v1/comparisons/{comparison_id}/analyses/routes-diff",
                  {
                    params,
                    body: frozen as components["schemas"]["RoutesRequest"],
                  },
                ),
              )
            : await unwrap(
                api.POST(
                  "/api/v1/comparisons/{comparison_id}/analyses/reachability-diff",
                  {
                    params,
                    body: frozen as components["schemas"]["ReachabilityDiffRequest"],
                  },
                ),
              );
      setJobId(submitted.id);
      attempt.current = null;
      setLocked(false);
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && knownRejection.has(caught.code)) {
        attempt.current = null;
        setLocked(false);
      }
    } finally {
      setBusy(false);
    }
  }
  const labels = {
    config: "分析配置文件差异",
    routes: "分析路由变化",
    reachability: "分析可达性变化",
  };
  const editable = !busy && !locked;
  return (
    <Space orientation="vertical" style={{ width: "100%" }} size="middle">
      <Card title={labels[kind]}>
        {kind === "config" ? (
          <p>无需额外条件。比较两份快照的原始配置文件文本。</p>
        ) : kind === "routes" ? (
          <AdvancedOptions activeCount={Number(!!node) + Number(!!prefix)}>
            <Space wrap>
              <label>
                设备表达式
                <Input
                  aria-label="设备表达式"
                  value={node}
                  disabled={!editable}
                  onChange={(event) => setNode(event.target.value)}
                  placeholder="可选，默认当前网络全部设备"
                />
              </label>
              <label>
                IPv4 路由前缀
                <Input
                  aria-label="IPv4 路由前缀"
                  value={prefix}
                  disabled={!editable}
                  onChange={(event) => setPrefix(event.target.value)}
                  placeholder="可选，如 10.64.0.0/24"
                />
              </label>
            </Space>
          </AdvancedOptions>
        ) : (
          <>
            <Space wrap>
              <label>
                目的 IPv4 范围
                <Input
                  aria-label="目的 IPv4 范围"
                  value={destination}
                  disabled={!editable}
                  onChange={(event) => setDestination(event.target.value)}
                  placeholder="必填，如 10.64.0.4"
                />
              </label>
              <label>
                起点设备或接口
                <Input
                  aria-label="起点设备或接口"
                  value={start}
                  disabled={!editable}
                  onChange={(event) => setStart(event.target.value)}
                  placeholder="必填，如 c1"
                />
              </label>
            </Space>
            <p className="muted">
              必须限定流量范围；空结果仅适用于填写的条件。
            </p>
            <AdvancedOptions
              activeCount={
                Number(!!source) +
                Number(protocols.join() !== "icmp") +
                Number(!!ports) +
                Number(maxTraces !== 5)
              }
            >
              <Space wrap>
                <label>
                  源 IPv4 范围
                  <Input
                    aria-label="源 IPv4 范围"
                    value={source}
                    disabled={!editable}
                    onChange={(event) => setSource(event.target.value)}
                    placeholder="可选"
                  />
                </label>
                <label>
                  IP 协议
                  <Select
                    aria-label="IP 协议"
                    mode="multiple"
                    virtual={false}
                    style={{ width: 180 }}
                    value={protocols}
                    disabled={!editable}
                    options={[
                      "icmp",
                      "tcp",
                      "udp",
                      "gre",
                      "esp",
                      "ah",
                      "ospf",
                      "sctp",
                      "ipinip",
                    ].map((value) => ({ value, label: value.toUpperCase() }))}
                    onChange={setProtocols}
                  />
                </label>
                <label>
                  目标端口
                  <Input
                    aria-label="目标端口"
                    value={ports}
                    disabled={!editable}
                    onChange={(event) => setPorts(event.target.value)}
                    placeholder="仅 TCP/UDP，可选"
                  />
                </label>
                <label>
                  每侧最多路径
                  <Select
                    aria-label="每侧最多路径"
                    style={{ width: 100 }}
                    value={maxTraces}
                    disabled={!editable}
                    options={[1, 2, 5, 10, 20].map((value) => ({
                      value,
                      label: String(value),
                    }))}
                    onChange={setMaxTraces}
                  />
                </label>
              </Space>
            </AdvancedOptions>
          </>
        )}
        {validation && <Alert type="error" title={validation} />}
        {error !== undefined && <ErrorState error={error} />}
        <Button
          type="primary"
          loading={busy}
          disabled={
            (kind === "reachability" &&
              (!destination.trim() || !start.trim())) ||
            (locked && !attempt.current)
          }
          onClick={() => void submit()}
        >
          {labels[kind]}
        </Button>
        {locked && (
          <p>提交结果未知。保持原参数与幂等键，重试可确认是否已创建任务。</p>
        )}
      </Card>
      {jobId && (
        <Card
          title="分析任务"
          extra={<Link to={`/jobs/${jobId}`}>查看任务详情</Link>}
        >
          {job.isError ? (
            <ErrorState error={job.error} retry={() => void job.refetch()} />
          ) : job.isPending ? (
            <LoadingState />
          ) : (
            <Space>
              <Tag>
                {job.data.status === "succeeded"
                  ? "已完成"
                  : job.data.status === "failed"
                    ? "计算失败"
                    : job.data.status === "interrupted"
                      ? "执行中断"
                      : job.data.status === "cancelled"
                        ? "已取消"
                        : "正在处理"}
              </Tag>
              <span>{job.data.id.slice(0, 8)}</span>
            </Space>
          )}
          {job.data &&
            ["failed", "interrupted", "cancelled"].includes(
              job.data.status,
            ) && (
              <Alert
                type="error"
                title="计算未完成；请查看任务详情中的失败原因，再修改范围或重试。"
              />
            )}
        </Card>
      )}
      {result.isError && (
        <ErrorState error={result.error} retry={() => void result.refetch()} />
      )}
      {result.data && (
        <ChangeResults
          key={result.data.id}
          comparison={comparison}
          result={result.data}
        />
      )}
    </Space>
  );
}

function ComparisonAnalysis({
  comparison,
  snapshotNames,
}: {
  comparison: Comparison;
  snapshotNames: Record<string, string>;
}) {
  const baseline =
    snapshotNames[comparison.baseline_snapshot_id] ??
    comparison.baseline_snapshot_id.slice(0, 8);
  const candidate =
    snapshotNames[comparison.candidate_snapshot_id] ??
    comparison.candidate_snapshot_id.slice(0, 8);
  return (
    <>
      <Card className="comparison-direction" title="固定比较方向">
        <div className="change-sides">
          <div>
            <Tag>左侧 · 基线</Tag>
            <strong>基线：{baseline}</strong>
            <p>{comparison.baseline_snapshot_id}</p>
          </div>
          <div>
            <Tag color="blue">右侧 · 候选</Tag>
            <strong>候选：{candidate}</strong>
            <p>{comparison.candidate_snapshot_id}</p>
          </div>
        </div>
        <p className="muted">
          候选相对基线的新增或消失；已有比较不会因上方草稿交换而改变。
        </p>
        {comparison.coverage !== "complete" && (
          <Alert
            type="warning"
            title="比较的模型覆盖有限；请先查看两份快照的解析诊断。"
          />
        )}
        {comparison.coverage_notes.map((note) => (
          <Alert type="warning" title={note} key={note} />
        ))}
      </Card>
      <Tabs
        className="comparison-tabs"
        defaultActiveKey="config"
        items={[
          {
            key: "config",
            label: "配置变化",
            children: <AnalysisPane comparison={comparison} kind="config" />,
          },
          {
            key: "routes",
            label: "路由变化",
            children: <AnalysisPane comparison={comparison} kind="routes" />,
          },
          {
            key: "reachability",
            label: "可达性变化",
            children: (
              <AnalysisPane comparison={comparison} kind="reachability" />
            ),
          },
        ]}
      />
    </>
  );
}

function NetworkChanges({ networkId }: { networkId: string }) {
  const [search] = useSearchParams();
  const handoff = useRef("");
  const session = useSession();
  const client = useQueryClient();
  const snapshots = useSnapshots(networkId);
  const allSnapshots =
    snapshots.data?.pages.flatMap((page) => page.items) ?? [];
  const snapshotNames = Object.fromEntries(
    allSnapshots.map((snapshot) => [snapshot.id, snapshot.display_name]),
  );
  const selectable = allSnapshots.filter(editableSnapshot);
  const [baselineId, setBaselineId] = useState<string>();
  const [candidateId, setCandidateId] = useState<string>();
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Comparison | null>(null);
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>();
  const [createLocked, setCreateLocked] = useState(false);
  const incomingBaseline = search.get("baseline");
  const incomingCandidate = search.get("candidate");
  useEffect(() => {
    if (
      !incomingBaseline ||
      !incomingCandidate ||
      incomingBaseline === incomingCandidate
    )
      return;
    const key = `${networkId}:${incomingBaseline}:${incomingCandidate}`;
    if (handoff.current === key) return;
    if (
      !selectable.some((item) => item.id === incomingBaseline) ||
      !selectable.some((item) => item.id === incomingCandidate)
    )
      return;
    handoff.current = key;
    setBaselineId(incomingBaseline);
    setCandidateId(incomingCandidate);
    setSelected(null);
  }, [incomingBaseline, incomingCandidate, networkId, selectable]);
  const comparisons = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "comparisons",
      { offset },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/comparisons", {
          signal,
          params: {
            path: { network_id: networkId },
            query: { offset, limit: 20 },
          },
        }),
      ),
  });
  async function create() {
    if (
      !baselineId ||
      !candidateId ||
      baselineId === candidateId ||
      creating ||
      createLocked
    )
      return;
    setCreateError(undefined);
    const body: components["schemas"]["CreateComparisonRequest"] = {
      baseline_snapshot_id: baselineId,
      candidate_snapshot_id: candidateId,
      ...(name.trim() ? { display_name: name.trim() } : {}),
    };
    setCreating(true);
    try {
      const comparison = await unwrap(
        api.POST("/api/v1/networks/{network_id}/comparisons", {
          params: { path: { network_id: networkId } },
          body,
        }),
      );
      setSelected(comparison);
      await client.invalidateQueries({
        queryKey: resourceKey(
          session?.user_id ?? null,
          { networkId, snapshotId: null },
          "comparisons",
          { offset },
        ),
      });
    } catch (caught) {
      setCreateError(caught);
      if (!(caught instanceof ApiError && knownRejection.has(caught.code)))
        setCreateLocked(true);
    } finally {
      setCreating(false);
    }
  }
  const options = selectable.map((snapshot) => ({
    value: snapshot.id,
    label: snapshot.display_name,
  }));
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">CHANGE WORKBENCH</div>
          <Typography.Title level={2}>变更对比</Typography.Title>
          <Typography.Paragraph type="secondary">
            选择两份就绪快照，按“变化摘要 → 双侧证据 → 原始信息”逐级审阅。
          </Typography.Paragraph>
        </div>
      </div>
      <Card title="创建比较" className="comparison-create">
        {handoff.current && (
          <Alert
            type="info"
            title="已带入故障方案的原始基线和派生快照；请确认方向，再创建比较并选择分析范围。"
          />
        )}
        <Space wrap align="end">
          <label>
            基线快照
            <Select
              aria-label="基线快照"
              virtual={false}
              showSearch
              style={{ width: 210 }}
              placeholder="选择变更前快照"
              value={baselineId}
              options={options}
              loading={snapshots.isFetching}
              disabled={createLocked}
              onChange={setBaselineId}
            />
          </label>
          <Button
            aria-label="交换基线与候选"
            disabled={!baselineId || !candidateId || createLocked}
            onClick={() => {
              setBaselineId(candidateId);
              setCandidateId(baselineId);
            }}
          >
            交换基线与候选
          </Button>
          <label>
            候选快照
            <Select
              aria-label="候选快照"
              virtual={false}
              showSearch
              style={{ width: 210 }}
              placeholder="选择变更后快照"
              value={candidateId}
              options={options}
              loading={snapshots.isFetching}
              disabled={createLocked}
              onChange={setCandidateId}
            />
          </label>
          <label>
            比较名称
            <Input
              aria-label="比较名称"
              value={name}
              disabled={createLocked}
              onChange={(event) => setName(event.target.value)}
              placeholder="可选"
            />
          </label>
          <Button
            type="primary"
            loading={creating}
            disabled={
              !baselineId ||
              !candidateId ||
              baselineId === candidateId ||
              createLocked
            }
            onClick={() => void create()}
          >
            创建比较
          </Button>
        </Space>
        {baselineId && baselineId === candidateId && (
          <Alert type="warning" title="基线和候选必须是不同快照。" />
        )}
        {createError instanceof ApiError &&
        createError.fieldErrors.some((field) =>
          field.message.includes("versions differ"),
        ) ? (
          <Alert
            type="error"
            title="两份快照的 Batfish 引擎或 SDK 版本不同，无法比较。请选择同版本初始化的快照。"
          />
        ) : createError !== undefined ? (
          <ErrorState error={createError} />
        ) : null}
        {createLocked && (
          <Alert
            type="warning"
            title="创建结果未知。请刷新比较记录确认后再尝试，避免重复创建。"
            action={
              <Button
                onClick={async () => {
                  const refreshed = await comparisons.refetch();
                  if (!refreshed.isError) {
                    setCreateLocked(false);
                    setCreateError(undefined);
                  }
                }}
              >
                刷新比较记录
              </Button>
            }
          />
        )}
        {snapshots.hasNextPage && (
          <Button onClick={() => void snapshots.fetchNextPage()}>
            加载更多快照
          </Button>
        )}
      </Card>
      <Card title="比较记录" className="comparison-list">
        {comparisons.isError ? (
          <ErrorState
            error={comparisons.error}
            retry={() => void comparisons.refetch()}
          />
        ) : comparisons.data?.total === 0 ? (
          <EmptyState
            title="尚无比较记录"
            description="选好基线与候选后创建第一条比较。"
          />
        ) : (
          <Table<Comparison>
            rowKey="id"
            loading={comparisons.isPending}
            dataSource={comparisons.data?.items}
            pagination={{
              current: offset / 20 + 1,
              pageSize: 20,
              total: comparisons.data?.total,
              showSizeChanger: false,
              onChange: (page) => setOffset((page - 1) * 20),
            }}
            columns={[
              {
                title: "比较",
                render: (_, item) => (
                  <span>
                    {item.display_name} · {item.id.slice(0, 8)}
                  </span>
                ),
              },
              {
                title: "基线（左）",
                render: (_, item) =>
                  snapshotNames[item.baseline_snapshot_id] ??
                  item.baseline_snapshot_id.slice(0, 8),
              },
              {
                title: "候选（右）",
                render: (_, item) =>
                  snapshotNames[item.candidate_snapshot_id] ??
                  item.candidate_snapshot_id.slice(0, 8),
              },
              {
                title: "覆盖",
                dataIndex: "coverage",
                render: (value: string) => (
                  <Tag color={value === "complete" ? "green" : "gold"}>
                    {value === "complete" ? "完整" : "有限"}
                  </Tag>
                ),
              },
              {
                title: "操作",
                render: (_, item) => (
                  <Button
                    aria-label={`选择比较 ${item.id}`}
                    onClick={() => setSelected(item)}
                  >
                    查看比较
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
      {selected && (
        <ComparisonAnalysis
          key={selected.id}
          comparison={selected}
          snapshotNames={snapshotNames}
        />
      )}
    </>
  );
}

export function ChangesPage() {
  const { network } = useResourceContext();
  return network ? (
    <NetworkChanges key={network.id} networkId={network.id} />
  ) : (
    <EmptyState
      title="先选择网络"
      description="在顶部选定网络后，可以创建和查看该网络的快照比较。"
    />
  );
}
