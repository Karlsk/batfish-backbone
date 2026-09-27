import { useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Steps,
  Tag,
  Typography,
} from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { resourceKey, useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { EmptyState, ErrorState } from "../../components/States";
import { useCandidates } from "../inventory/useCandidates";
import { pollInterval } from "../jobs/model";
import { useSnapshots } from "../networks/queries";

type Target = components["schemas"]["InterfaceTarget"];
type Request = components["schemas"]["FaultScenarioRequest"];
type Created = components["schemas"]["SnapshotCreated"];
const editable = (status: string) =>
  status === "ready" || status === "ready_with_warnings";
const knownRejection = new Set([
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "NOT_READY",
  "CONFLICT",
  "FORBIDDEN",
  "RATE_LIMITED",
]);

function FaultWizard({
  networkId,
  baselineId,
  baselineName,
}: {
  networkId: string;
  baselineId: string;
  baselineName: string;
}) {
  const session = useSession();
  const client = useQueryClient();
  const candidates = useCandidates(networkId, baselineId);
  const [name, setName] = useState("");
  const [nodes, setNodes] = useState<string[]>([]);
  const [interfaceNode, setInterfaceNode] = useState("");
  const [interfaceName, setInterfaceName] = useState("");
  const [interfaces, setInterfaces] = useState<Target[]>([]);
  const [created, setCreated] = useState<Created | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [validation, setValidation] = useState("");
  const flight = useRef(false);
  const attempt = useRef<{ key: string; body: Request } | null>(null);
  const frozen = busy || !!created || !!attempt.current;
  const context = { networkId, snapshotId: baselineId };
  const job = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "fault-job",
      {},
      created?.job_id,
    ),
    enabled: !!created,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/jobs/{job_id}", {
          signal,
          params: { path: { job_id: created!.job_id } },
        }),
      ),
    refetchInterval: (query) => pollInterval(query.state.data),
  });
  const derived = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "fault-derived",
      {},
      created?.snapshot_id,
    ),
    enabled: job.data?.status === "succeeded" && !!created,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: {
            path: { network_id: networkId, snapshot_id: created!.snapshot_id },
          },
        }),
      ),
    refetchInterval: (query) =>
      ["queued", "initializing"].includes(query.state.data?.status ?? "")
        ? 2000
        : false,
  });
  const successful =
    job.data?.status === "succeeded" &&
    !!derived.data &&
    editable(derived.data.status);
  const failed =
    job.data &&
    ["failed", "cancelled", "interrupted"].includes(job.data.status);
  async function submit() {
    if (flight.current || created) return;
    setValidation("");
    setError(undefined);
    const displayName = name.trim();
    if (!displayName || (!nodes.length && !interfaces.length)) {
      setValidation("填写方案名称，并至少选择一台设备或一个接口。");
      return;
    }
    attempt.current ??= {
      key: crypto.randomUUID(),
      body: {
        display_name: displayName,
        deactivate_nodes: nodes,
        deactivate_interfaces: interfaces,
      },
    };
    flight.current = true;
    setBusy(true);
    try {
      const result = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/fault-scenarios",
          {
            params: {
              path: { network_id: networkId, snapshot_id: baselineId },
              header: { "idempotency-key": attempt.current.key },
            },
            body: attempt.current.body,
          },
        ),
      );
      setCreated(result);
      attempt.current = null;
      await client.invalidateQueries({
        queryKey: resourceKey(
          session?.user_id ?? null,
          { networkId, snapshotId: null },
          "snapshots",
        ),
      });
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && knownRejection.has(caught.code))
        attempt.current = null;
    } finally {
      flight.current = false;
      setBusy(false);
    }
  }
  return (
    <Space orientation="vertical" size="large" style={{ width: "100%" }}>
      <Card title="选择模拟对象" className="fault-card">
        <p className="muted">
          先从当前基线读取设备与接口；也可输入已知的完整设备名称。
        </p>
        {candidates.controls}
        <div className="fault-fields">
          <label>
            停用设备
            <Select
              aria-label="停用设备"
              mode="tags"
              virtual={false}
              showSearch
              value={nodes}
              options={candidates.nodes.map((node) => ({
                value: node,
                label: node,
              }))}
              disabled={frozen}
              placeholder="选择或输入设备名称"
              onChange={(values) => {
                const distinct = [
                  ...new Set(values.map((item) => item.trim()).filter(Boolean)),
                ];
                setNodes(distinct);
                setInterfaces((current) =>
                  current.filter((target) => !distinct.includes(target.node)),
                );
              }}
            />
          </label>
          <label>
            接口所在设备
            <Select
              aria-label="接口所在设备"
              virtual={false}
              showSearch
              value={interfaceNode || undefined}
              disabled={frozen}
              options={candidates.nodes.map((node) => ({
                value: node,
                label: node,
              }))}
              placeholder="先选设备"
              onChange={(value) => {
                setInterfaceNode(value);
                setInterfaceName("");
              }}
            />
          </label>
          <label>
            接口名称
            <Select
              aria-label="接口名称"
              virtual={false}
              showSearch
              value={interfaceName || undefined}
              disabled={frozen || !interfaceNode}
              options={candidates
                .interfaces([interfaceNode])
                .map((value) => ({ value, label: value }))}
              placeholder="再选接口"
              onChange={setInterfaceName}
            />
          </label>
          <Button
            disabled={
              frozen ||
              !interfaceNode ||
              !interfaceName ||
              nodes.includes(interfaceNode)
            }
            onClick={() => {
              const target = { node: interfaceNode, interface: interfaceName };
              setInterfaces((current) =>
                current.some(
                  (item) =>
                    item.node === target.node &&
                    item.interface === target.interface,
                )
                  ? current
                  : [...current, target],
              );
              setInterfaceName("");
            }}
          >
            加入接口
          </Button>
        </div>
        {interfaces.length > 0 && (
          <div className="fault-targets">
            {interfaces.map((target) => (
              <Tag
                key={`${target.node}:${target.interface}`}
                closable={!frozen}
                onClose={() =>
                  setInterfaces((current) =>
                    current.filter(
                      (item) =>
                        item.node !== target.node ||
                        item.interface !== target.interface,
                    ),
                  )
                }
              >
                {target.node} · {target.interface}
              </Tag>
            ))}
          </div>
        )}
      </Card>
      <Card title="确认派生关系" className="fault-card fault-preview">
        <div className="change-sides">
          <div>
            <span className="eyebrow">基线 · 原始配置</span>
            <strong>{baselineName}</strong>
            <p>原始基线保持不变，可以随时返回查看。</p>
          </div>
          <div>
            <span className="eyebrow">候选 · 模型故障</span>
            <strong>{name.trim() || "待命名方案"}</strong>
            <p>
              {nodes.length} 台设备、{interfaces.length} 个接口将被停用。
            </p>
          </div>
        </div>
        <Alert
          type="info"
          title="仅在 Batfish 模型中模拟，不会操作真实设备。"
        />
        <label className="fault-name">
          方案名称
          <Input
            aria-label="方案名称"
            value={name}
            disabled={frozen}
            onChange={(event) => setName(event.target.value)}
            placeholder="例如：断开核心设备 c1"
          />
        </label>
        {validation && <Alert type="warning" title={validation} />}
        {error !== undefined && <ErrorState error={error} />}
        {attempt.current && !busy && !created && (
          <Alert
            type="warning"
            title="创建结果暂未确认；请使用相同请求重试，避免重复派生。"
          />
        )}
        <Button
          type="primary"
          loading={busy}
          disabled={!!created}
          onClick={() => void submit()}
        >
          {attempt.current ? "重试创建派生快照" : "创建派生快照"}
        </Button>
      </Card>
      {created && (
        <Card title="派生任务" className="fault-card">
          <Space orientation="vertical">
            <span>任务状态：{job.data?.status ?? "正在查询"}</span>
            <Link to={`/jobs/${created.job_id}`}>查看任务详情</Link>
            {job.data?.status === "succeeded" &&
              !derived.data &&
              !derived.error && <span>正在确认派生快照的初始化质量…</span>}
            {derived.data && <span>快照状态：{derived.data.status}</span>}
            {job.error && (
              <ErrorState error={job.error} retry={() => void job.refetch()} />
            )}
            {failed && (
              <ErrorState
                error={
                  job.data?.error
                    ? new ApiError(
                        job.data.error.code,
                        job.data.error.request_id,
                        job.data.error.field_errors,
                      )
                    : new ApiError("ENGINE_QUERY_FAILED")
                }
              />
            )}
            {job.data?.status === "succeeded" && derived.error && (
              <ErrorState
                error={derived.error}
                retry={() => void derived.refetch()}
              />
            )}
            {derived.data?.status === "failed" && (
              <Alert
                type="error"
                title="派生快照初始化失败，请查看任务和快照诊断。"
              />
            )}
            {derived.data?.status === "ready_with_warnings" && (
              <Alert
                type="warning"
                title="派生快照包含解析或模型警告，请先查看诊断再判断影响。"
              />
            )}
            {derived.data && (
              <Link
                to={`/networks/${networkId}/snapshots/${created.snapshot_id}/diagnostics`}
              >
                查看派生快照诊断
              </Link>
            )}
            {successful && (
              <>
                <Alert
                  type="success"
                  title="派生快照已就绪。进入比较页后，仍需确认分析类型和范围。"
                />
                <Link
                  to={`/changes?baseline=${encodeURIComponent(baselineId)}&candidate=${encodeURIComponent(created.snapshot_id)}`}
                >
                  进入影响分析
                </Link>
              </>
            )}
          </Space>
        </Card>
      )}
    </Space>
  );
}

export function FaultsPage() {
  const { network } = useResourceContext();
  const snapshots = useSnapshots(network?.id ?? null);
  const [baselineId, setBaselineId] = useState<string>();
  if (!network)
    return (
      <EmptyState title="先选择网络" description="选定网络后再创建故障方案。" />
    );
  const all = snapshots.data?.pages.flatMap((page) => page.items) ?? [];
  const ready = all.filter((snapshot) => editable(snapshot.status));
  const baseline = ready.find((snapshot) => snapshot.id === baselineId);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">FAULT SCENARIO WORKBENCH</div>
          <Typography.Title level={2}>故障模拟</Typography.Title>
          <Typography.Paragraph type="secondary">
            从一份就绪配置出发，在模型中停用设备或接口，预览影响，再按需比较。
          </Typography.Paragraph>
        </div>
        <Tag color="blue">模型推演</Tag>
      </div>
      <Card title="选择基线" className="fault-card">
        <Steps
          size="small"
          current={baseline ? 1 : 0}
          items={[
            { title: "选择基线" },
            { title: "选择对象" },
            { title: "创建派生快照" },
            { title: "确认影响范围" },
          ]}
        />
        <label className="fault-baseline">
          基线快照
          <Select
            aria-label="基线快照"
            virtual={false}
            showSearch
            value={baselineId}
            loading={snapshots.isFetching}
            options={ready.map((snapshot) => ({
              value: snapshot.id,
              label: snapshot.display_name,
            }))}
            placeholder="选择一份已就绪快照"
            onChange={setBaselineId}
          />
        </label>
        {snapshots.error && (
          <ErrorState
            error={snapshots.error}
            retry={() => void snapshots.refetch()}
          />
        )}
        {snapshots.hasNextPage && (
          <Button onClick={() => void snapshots.fetchNextPage()}>
            加载更多快照
          </Button>
        )}
        {snapshots.isSuccess && !ready.length && (
          <EmptyState
            title="暂无可用基线"
            description="先上传并初始化一份配置快照。"
          />
        )}
      </Card>
      {baseline && (
        <FaultWizard
          key={`${network.id}:${baseline.id}`}
          networkId={network.id}
          baselineId={baseline.id}
          baselineName={baseline.display_name}
        />
      )}
    </>
  );
}
