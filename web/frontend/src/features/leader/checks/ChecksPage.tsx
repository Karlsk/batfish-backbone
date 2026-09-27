import { useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Empty,
  Input,
  InputNumber,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, unwrap } from "../../../api/client";
import type { components } from "../../../api/schema";
import { chooseEntry } from "../../../app/entry";
import { resourceKey, useResourceContext } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ErrorState, LoadingState } from "../../../components/States";
import { useNetworks, useSnapshots } from "../../networks/queries";
import {
  describeRun,
  runStatusLabels,
  engineStateLabels,
  coverageLabels,
  prepareMvpCheck,
  type MvpDraft,
  type MvpTemplateId,
} from "./model";

type Concern = components["schemas"]["ConcernDTO"];

const ids: MvpTemplateId[] = [
  "configuration-quality",
  "devices",
  "interfaces",
  "routes",
  "lpm-routes",
  "traceroute",
];
const labels: Record<MvpTemplateId, string> = {
  "configuration-quality": "配置质量",
  devices: "设备清单",
  interfaces: "接口清单",
  routes: "路由检查",
  "lpm-routes": "最长前缀匹配",
  traceroute: "虚拟连通性",
};
const descriptions: Record<MvpTemplateId, string> = {
  "configuration-quality": "先看配置是否解析，以及模型已知限制。",
  devices: "查看快照里识别出的设备。",
  interfaces: "查看已建模的接口状态与地址。",
  routes: "按一个明确网段检查路由记录。",
  "lpm-routes": "检查一个目的地址命中的最长前缀。",
  traceroute: "从一个起点推演到一个目的地的单向路径。",
};
const short = (value: string) => value.slice(0, 8);
const when = (value: string) =>
  new Date(value).toLocaleString("zh-CN", { hour12: false });

export function LeaderChecksPage() {
  const { runId } = useParams();
  return runId ? <CheckRunDetail runId={runId} /> : <CheckWorkspace />;
}

function CheckWorkspace() {
  const session = useSession();
  const { network, snapshot } = useResourceContext();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [networkId, setNetworkId] = useState<string | null>(
    network?.id ?? null,
  );
  const [snapshotId, setSnapshotId] = useState<string | null>(
    snapshot?.id ?? null,
  );
  const [templateId, setTemplateId] = useState<MvpTemplateId>(
    "configuration-quality",
  );
  const [draft, setDraft] = useState<MvpDraft>({});
  const [concernId, setConcernId] = useState<string | null>(null);
  const [flowIndex, setFlowIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<unknown>(null);
  const networks = useNetworks();
  const snapshots = useSnapshots(networkId);
  const networkRows = networks.data?.pages.flatMap((page) => page.items) ?? [];
  const readySnapshots =
    snapshots.data?.pages
      .flatMap((page) => page.items)
      .filter(
        (item) =>
          item.status === "ready" || item.status === "ready_with_warnings",
      ) ?? [];
  const selectedNetwork = networkRows.find((item) => item.id === networkId);
  const selectedSnapshot = readySnapshots.find(
    (item) => item.id === snapshotId,
  );
  const templates = useQuery({
    queryKey: ["leader-check-templates", session?.user_id],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/leader/check-templates", { signal })),
    enabled: !!session,
  });
  const concerns = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "leader-check-concerns",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/business-concerns", {
          signal,
          params: { query: { network_id: networkId!, offset: 0, limit: 200 } },
        }),
      ),
    enabled: !!session && !!networkId && templateId === "traceroute",
  });
  const concernRows = concerns.data?.items ?? [];
  const selectedConcern = concernRows.find((item) => item.id === concernId);
  const runs = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "leader-check-runs",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/leader/check-runs", {
          signal,
          params: {
            query: { network_id: networkId ?? undefined, offset: 0, limit: 20 },
          },
        }),
      ),
    enabled: !!session,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) =>
        ["submitting", "queued", "running"].includes(item.status),
      )
        ? 2500
        : false,
  });
  const template = templates.data?.items.find((item) => item.id === templateId);

  const prefill = (concern: Concern, index: number) => {
    const flow = concern.flows[index];
    if (!flow) return;
    setConcernId(concern.id);
    setFlowIndex(index);
    setDraft((current) => ({
      ...current,
      start_location: flow.start_location,
      destination_ip: flow.destination_ip,
      source_ip: flow.source_ip ?? "",
      protocol: flow.protocol ?? undefined,
      destination_port: flow.destination_port ?? null,
    }));
    setFormError(null);
  };
  const submit = async () => {
    if (busyRef.current) return;
    setFormError(null);
    setRequestError(null);
    if (!networkId || !snapshotId || !selectedSnapshot) {
      setFormError("请选择网络与已就绪的配置快照");
      return;
    }
    let prepared;
    try {
      prepared = prepareMvpCheck(templateId, draft);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "请检查输入范围");
      return;
    }
    const body = {
      template_id: templateId,
      network_id: networkId,
      snapshot_id: snapshotId,
      scope: prepared.scope,
      options: prepared.options,
      ...(templateId === "traceroute" && selectedConcern
        ? {
            concern_id: selectedConcern.id,
            concern_version: selectedConcern.version,
          }
        : {}),
    };
    const signature = JSON.stringify(body);
    if (attempt.current?.signature !== signature)
      attempt.current = { signature, key: crypto.randomUUID() };
    busyRef.current = true;
    setBusy(true);
    try {
      const created = await unwrap(
        api.POST("/api/v1/leader/check-runs", {
          params: { header: { "idempotency-key": attempt.current.key } },
          body,
        }),
      );
      void client.invalidateQueries({
        queryKey: resourceKey(
          session?.user_id ?? null,
          { networkId, snapshotId: null },
          "leader-check-runs",
        ),
      });
      navigate(`/leader/checks/${created.id}`);
    } catch (error) {
      setRequestError(error);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <section className="leader-checks-page">
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">GUIDED CHECK / 自主检查</span>
          <Typography.Title level={1}>自主检查</Typography.Title>
          <p>
            从一个已就绪的配置快照出发，只回答当前问题。结论保留范围、来源和模型边界。
          </p>
        </div>
        <Link to="/leader/overview">
          返回总览 <ArrowRightOutlined />
        </Link>
      </div>
      <div className="leader-checks-steps">
        <span>01 选择网络与快照</span>
        <span>02 选择问题与范围</span>
        <span>03 读取结论与证据</span>
      </div>
      <Card className="leader-checks-panel" title="检查来源">
        <div className="leader-checks-pickers">
          <label>
            检查网络
            <Select
              aria-label="检查网络"
              value={networkId}
              placeholder="选择一个共享网络"
              showSearch={{ optionFilterProp: "label" }}
              virtual={false}
              options={networkRows.map((item) => ({
                value: item.id,
                label: `${item.display_name} · ${short(item.id)}`,
                disabled: item.sync_state !== "ready",
              }))}
              onChange={(value) => {
                setNetworkId(value);
                setSnapshotId(null);
                setConcernId(null);
                setDraft({});
                setFormError(null);
              }}
            />
          </label>
          <label>
            配置快照
            <Select
              aria-label="配置快照"
              value={snapshotId}
              placeholder="选择已就绪快照"
              disabled={!networkId}
              showSearch={{ optionFilterProp: "label" }}
              virtual={false}
              options={readySnapshots.map((item) => ({
                value: item.id,
                label: `${item.display_name} · ${short(item.id)}${item.status === "ready_with_warnings" ? " · 有警告" : ""}`,
              }))}
              onChange={(value) => {
                setSnapshotId(value);
                setFormError(null);
              }}
            />
          </label>
        </div>
        {networks.hasNextPage && (
          <Button onClick={() => void networks.fetchNextPage()}>
            加载更多网络
          </Button>
        )}
        {snapshots.hasNextPage && (
          <Button onClick={() => void snapshots.fetchNextPage()}>
            加载更多快照
          </Button>
        )}
        {networks.isError && (
          <ErrorState
            error={networks.error}
            retry={() => void networks.refetch()}
          />
        )}
        {snapshots.isError && (
          <ErrorState
            error={snapshots.error}
            retry={() => void snapshots.refetch()}
          />
        )}
        {selectedSnapshot && (
          <div className="leader-checks-source">
            <Tag
              color={
                selectedSnapshot.status === "ready_with_warnings"
                  ? "gold"
                  : "blue"
              }
            >
              {selectedSnapshot.status === "ready_with_warnings"
                ? "有解析警告"
                : "已就绪"}
            </Tag>
            <strong>
              {selectedNetwork?.display_name ?? short(networkId!)} /{" "}
              {selectedSnapshot.display_name}
            </strong>
            <span>
              固定快照 {short(selectedSnapshot.id)} ·{" "}
              {when(selectedSnapshot.created_at)}
            </span>
          </div>
        )}
      </Card>
      <div className="leader-overview-section-head">
        <div>
          <h2>想检查什么？</h2>
          <p>先选问题，再填写必要范围。未检查的项目不会自动变成“正常”。</p>
        </div>
      </div>
      {templates.isError && (
        <ErrorState
          error={templates.error}
          retry={() => void templates.refetch()}
        />
      )}
      <div
        className="leader-checks-templates"
        role="group"
        aria-label="检查问题"
      >
        {ids.map((id) => (
          <button
            key={id}
            type="button"
            className={
              templateId === id
                ? "leader-check-template selected"
                : "leader-check-template"
            }
            aria-pressed={templateId === id}
            onClick={() => {
              setTemplateId(id);
              setFormError(null);
              setConcernId(null);
            }}
          >
            <span>{labels[id]}</span>
            <small>{descriptions[id]}</small>
          </button>
        ))}
      </div>
      <Card
        className="leader-checks-panel"
        title={`${labels[templateId]} · 检查范围`}
      >
        <p className="leader-checks-note">
          {template?.model_note ??
            "基于固定快照的配置模型推演，不代表在线设备状态。"}
        </p>
        {templateId === "routes" && (
          <label className="leader-checks-field">
            要检查的 IPv4 网段
            <Input
              aria-label="要检查的 IPv4 网段"
              placeholder="例如 10.0.0.0/24"
              value={draft.network ?? ""}
              onChange={(event) =>
                setDraft({ ...draft, network: event.target.value })
              }
            />
          </label>
        )}
        {templateId === "lpm-routes" && (
          <label className="leader-checks-field">
            目的 IPv4 地址
            <Input
              aria-label="目的 IPv4 地址"
              placeholder="例如 10.0.0.2"
              value={draft.ip ?? ""}
              onChange={(event) =>
                setDraft({ ...draft, ip: event.target.value })
              }
            />
          </label>
        )}
        {templateId === "traceroute" && (
          <>
            <div className="leader-checks-fields">
              <label className="leader-checks-field">
                起点设备或接口
                <Input
                  aria-label="起点设备或接口"
                  placeholder="例如 r1"
                  value={draft.start_location ?? ""}
                  onChange={(event) => {
                    setDraft({
                      ...draft,
                      start_location: event.target.value,
                      protocol: undefined,
                      destination_port: null,
                    });
                    setConcernId(null);
                  }}
                />
              </label>
              <label className="leader-checks-field">
                目的 IPv4 地址
                <Input
                  aria-label="目的 IPv4 地址"
                  placeholder="例如 10.0.0.2"
                  value={draft.destination_ip ?? ""}
                  onChange={(event) => {
                    setDraft({
                      ...draft,
                      destination_ip: event.target.value,
                      protocol: undefined,
                      destination_port: null,
                    });
                    setConcernId(null);
                  }}
                />
              </label>
            </div>
            {concerns.isError && (
              <ErrorState
                error={concerns.error}
                retry={() => void concerns.refetch()}
              />
            )}
            {!!concernRows.length && (
              <div className="leader-checks-concern">
                <label>
                  从业务关注项预填（仍需核对本次范围）
                  <Select
                    aria-label="业务关注项"
                    allowClear
                    virtual={false}
                    placeholder="可选：使用已有关键流量"
                    value={concernId}
                    options={concernRows.map((item) => ({
                      value: item.id,
                      label: `${item.name} · 第 ${item.version} 版`,
                    }))}
                    onChange={(value) => {
                      const item = concernRows.find((row) => row.id === value);
                      if (item) prefill(item, 0);
                      else setConcernId(null);
                    }}
                  />
                </label>
                {selectedConcern && selectedConcern.flows.length > 1 && (
                  <Select
                    aria-label="关键流量"
                    virtual={false}
                    value={flowIndex}
                    options={selectedConcern.flows.map((flow, index) => ({
                      value: index,
                      label: `${flow.start_location} → ${flow.destination_ip}`,
                    }))}
                    onChange={(value) => prefill(selectedConcern, value)}
                  />
                )}
              </div>
            )}
            {selectedConcern && (
              <Alert
                type="info"
                showIcon
                title={`已预填 ${selectedConcern.name} 第 ${selectedConcern.version} 版；请核对起点、目的和当前快照。`}
              />
            )}
          </>
        )}
        {templateId !== "configuration-quality" && (
          <Collapse
            className="leader-checks-advanced"
            destroyOnHidden={false}
            items={[
              {
                key: "advanced",
                label: (
                  <span>
                    高级条件{" "}
                    <Tag>
                      {[
                        draft.nodes,
                        draft.vrfs,
                        draft.source_ip,
                        draft.max_traces,
                      ].filter(
                        (value) =>
                          value !== undefined && value !== null && value !== "",
                      ).length
                        ? `已生效 ${[draft.nodes, draft.vrfs, draft.source_ip, draft.max_traces].filter((value) => value !== undefined && value !== null && value !== "").length} 项`
                        : "使用默认值"}
                    </Tag>
                  </span>
                ),
                children: (
                  <div className="leader-checks-fields">
                    {["devices", "interfaces", "routes", "lpm-routes"].includes(
                      templateId,
                    ) && (
                      <label className="leader-checks-field">
                        只看这些设备（逗号分隔）
                        <Input
                          aria-label="只看这些设备"
                          value={draft.nodes ?? ""}
                          onChange={(event) =>
                            setDraft({ ...draft, nodes: event.target.value })
                          }
                          placeholder="留空为全部设备"
                        />
                      </label>
                    )}
                    {["routes", "lpm-routes"].includes(templateId) && (
                      <label className="leader-checks-field">
                        只看这些 VRF（逗号分隔）
                        <Input
                          aria-label="只看这些 VRF"
                          value={draft.vrfs ?? ""}
                          onChange={(event) =>
                            setDraft({ ...draft, vrfs: event.target.value })
                          }
                          placeholder="留空为全部 VRF"
                        />
                      </label>
                    )}
                    {templateId === "traceroute" && (
                      <>
                        <label className="leader-checks-field">
                          源 IPv4 地址
                          <Input
                            aria-label="源 IPv4 地址"
                            value={draft.source_ip ?? ""}
                            onChange={(event) => {
                              setDraft({
                                ...draft,
                                source_ip: event.target.value,
                                protocol: undefined,
                                destination_port: null,
                              });
                              setConcernId(null);
                            }}
                            placeholder="可选"
                          />
                        </label>
                        <label className="leader-checks-field">
                          最多返回路径
                          <InputNumber
                            aria-label="最多返回路径"
                            min={1}
                            max={20}
                            value={draft.max_traces ?? null}
                            onChange={(value) =>
                              setDraft({ ...draft, max_traces: value })
                            }
                            placeholder="默认 5"
                          />
                        </label>
                      </>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
        <div className="leader-checks-actions">
          <div>
            {selectedSnapshot ? (
              <span>
                即将使用 <strong>{selectedSnapshot.display_name}</strong>
                ，来源不会随页面切换而改变。
              </span>
            ) : (
              <span>请选择已就绪快照。</span>
            )}
          </div>
          <Button
            type="primary"
            size="large"
            icon={<PlayCircleOutlined />}
            loading={busy}
            disabled={!snapshotId || !selectedSnapshot}
            onClick={() => void submit()}
          >
            开始检查
          </Button>
        </div>
        {formError && <Alert type="warning" showIcon title={formError} />}
        {requestError !== null && (
          <ErrorState error={requestError} retry={() => void submit()} />
        )}
      </Card>
      <Card className="leader-checks-panel" title="最近的检查">
        <p className="leader-checks-note">
          刷新或离开后可从这里继续查看；历史运行保留原快照与参数。
        </p>
        {runs.isError && (
          <ErrorState error={runs.error} retry={() => void runs.refetch()} />
        )}
        {runs.isPending ? (
          <LoadingState />
        ) : runs.data?.items.length ? (
          <div className="leader-checks-history">
            {runs.data.items.map((item) => (
              <Link key={item.id} to={`/leader/checks/${item.id}`}>
                <strong>
                  {labels[item.template_id as MvpTemplateId] ??
                    item.template_id}
                </strong>
                <span>
                  {runStatusLabels[item.status]} · {when(item.created_at)} ·
                  快照 {short(item.snapshot_id)}
                </span>
                <ArrowRightOutlined />
              </Link>
            ))}
          </div>
        ) : (
          <Empty description="尚未运行检查" />
        )}
        {runs.data && runs.data.total > runs.data.items.length && (
          <p>仅显示最近 {runs.data.items.length} 条，请选择网络缩小范围。</p>
        )}
      </Card>
    </section>
  );
}

function CheckRunDetail({ runId }: { runId: string }) {
  const session = useSession();
  const client = useQueryClient();
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelError, setCancelError] = useState<unknown>(null);
  const runQuery = useQuery({
    queryKey: ["leader-check-run", session?.user_id, runId],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/leader/check-runs/{run_id}", {
          signal,
          params: { path: { run_id: runId } },
        }),
      ),
    enabled: !!session,
    refetchInterval: (query) =>
      ["submitting", "queued", "running"].includes(
        query.state.data?.status ?? "",
      )
        ? 2500
        : false,
  });
  const run = runQuery.data;
  const resultId = run?.result_ids[0];
  const resultQuery = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      {
        networkId: run?.network_id ?? null,
        snapshotId: run?.snapshot_id ?? null,
      },
      "leader-check-result",
      {},
      resultId ?? null,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}", {
          signal,
          params: { path: { result_id: resultId! } },
        }),
      ),
    enabled: !!session && !!resultId,
  });
  if (runQuery.isPending) return <LoadingState />;
  if (runQuery.isError)
    return (
      <ErrorState
        error={runQuery.error}
        retry={() => void runQuery.refetch()}
      />
    );
  if (!run) return null;
  const result =
    resultQuery.data?.context.snapshot_id === run.snapshot_id
      ? resultQuery.data
      : null;
  const sourceMismatch = !!resultQuery.data && !result;
  const view = describeRun(run, result ?? null);
  const cancelJob = run.jobs.find((item) => item.status === "queued");
  const scope = run.effective_parameters.request;
  const values =
    scope && typeof scope === "object" && !Array.isArray(scope)
      ? (scope as Record<string, unknown>)
      : {};
  const cancel = async () => {
    if (!cancelJob || cancelBusy) return;
    setCancelBusy(true);
    setCancelError(null);
    try {
      await unwrap(
        api.POST("/api/v1/jobs/{job_id}/cancel", {
          params: { path: { job_id: cancelJob.id } },
        }),
      );
      void client.invalidateQueries({
        queryKey: ["leader-check-run", session?.user_id, runId],
      });
    } catch (error) {
      setCancelError(error);
    } finally {
      setCancelBusy(false);
    }
  };
  return (
    <section className="leader-checks-page leader-check-detail">
      <Link className="leader-back-link" to="/leader/checks">
        <ArrowLeftOutlined /> 返回自主检查
      </Link>
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">CHECK RECORD / 固定检查</span>
          <Typography.Title level={1}>
            {labels[run.template_id as MvpTemplateId] ?? "检查记录"}
          </Typography.Title>
          <p>
            运行编号 {run.id} · {when(run.created_at)}
          </p>
        </div>
        <Tag
          color={
            run.status === "succeeded"
              ? "blue"
              : run.status === "failed" || run.status === "interrupted"
                ? "red"
                : "gold"
          }
        >
          {runStatusLabels[run.status]}
        </Tag>
      </div>
      <Card className="leader-checks-conclusion">
        <span className="leader-kicker">01 / 结论</span>
        <Typography.Title level={2}>{view.headline}</Typography.Title>
        {view.facts.length > 0 && (
          <div className="leader-checks-facts">
            {view.facts.map((fact) => (
              <span key={fact}>{fact}</span>
            ))}
          </div>
        )}
        {view.warnings.map((warning) => (
          <Alert key={warning} type="warning" showIcon title={warning} />
        ))}
        {sourceMismatch && (
          <Alert
            type="error"
            showIcon
            title="结果来源与本次固定快照不一致，请在技术工作台核对任务。"
          />
        )}
        {resultQuery.isError && (
          <ErrorState
            error={resultQuery.error}
            retry={() => void resultQuery.refetch()}
          />
        )}
      </Card>
      <div className="leader-checks-detail-grid">
        <Card title="02 / 本次检查范围" className="leader-checks-panel">
          <p>
            网络 {short(run.network_id)} · 固定快照 {short(run.snapshot_id)}
          </p>
          {run.template_id === "routes" && (
            <p>
              网段：
              {String(
                values.options &&
                  typeof values.options === "object" &&
                  !Array.isArray(values.options)
                  ? ((values.options as Record<string, unknown>).network ??
                      "未记录")
                  : "未记录",
              )}
            </p>
          )}
          {run.template_id === "lpm-routes" && (
            <p>目标地址：{String(values.ip ?? "未记录")}</p>
          )}
          {run.template_id === "traceroute" && (
            <p>
              起点 {String(values.start_location ?? "未记录")} → 目的{" "}
              {String(values.destination_ip ?? "未记录")}
            </p>
          )}
          {run.frozen_concern && (
            <p>
              业务关注项：{String(run.frozen_concern.name ?? "未命名")} · 第{" "}
              {run.concern_version} 版
            </p>
          )}
          <p className="leader-checks-note">
            这里只说明显式检查范围，不能推断范围外的业务是否受影响。
          </p>
        </Card>
        <Card title="03 / 证据与进度" className="leader-checks-panel">
          {run.jobs.map((job) => (
            <p key={job.id}>
              任务 {short(job.id)} · {runStatusLabels[job.status]} · 阶段{" "}
              {job.phase} · 引擎 {engineStateLabels[job.engine_state]}
            </p>
          ))}
          {run.status === "submitting" && <p>正在保存检查任务…</p>}
          {result && (
            <>
              <p>
                结果 {short(result.id)} · {when(result.created_at)}
              </p>
              <p>
                覆盖：{coverageLabels[result.coverage]} ·{" "}
                {result.truncated ? "已截断" : "未截断"}
              </p>
            </>
          )}
          {run.template_id === "configuration-quality" && (
            <p>解析事实来自创建检查时选定的快照。</p>
          )}
          {cancelJob && run.created_by === session?.user_id && (
            <Button loading={cancelBusy} onClick={() => void cancel()}>
              取消排队任务
            </Button>
          )}
          {cancelError !== null && (
            <ErrorState error={cancelError} retry={() => void cancel()} />
          )}
        </Card>
      </div>
      <Card title="04 / 查看技术详情" className="leader-checks-panel">
        <Space wrap>
          {run.template_id === "configuration-quality" && (
            <Link
              to={`/networks/${run.network_id}/snapshots/${run.snapshot_id}/diagnostics`}
              onClick={() => chooseEntry("technical")}
            >
              查看解析证据 <ArrowRightOutlined />
            </Link>
          )}
          {result && (
            <Link
              to={`/results/${result.id}`}
              onClick={() => chooseEntry("technical")}
            >
              {run.template_id === "traceroute"
                ? "查看完整路径证据"
                : "查看完整结果与导出"}{" "}
              <ArrowRightOutlined />
            </Link>
          )}
          {run.jobs[0] && (
            <Link
              to={`/jobs/${run.jobs[0].id}`}
              onClick={() => chooseEntry("technical")}
            >
              查看任务详情 <ArrowRightOutlined />
            </Link>
          )}
          {run.template_id !== "configuration-quality" && (
            <Link
              to={
                run.template_id === "traceroute"
                  ? "/traceroute"
                  : `/analysis/${run.template_id === "devices" ? "nodes" : run.template_id}`
              }
              onClick={() => chooseEntry("technical")}
            >
              打开技术检查页 <ArrowRightOutlined />
            </Link>
          )}
        </Space>
        <Collapse
          className="leader-checks-raw"
          items={[
            {
              key: "source",
              label: "固定参数与版本",
              children: (
                <pre>
                  {JSON.stringify(
                    {
                      snapshot_id: run.snapshot_id,
                      template_version: run.template_version,
                      concern_version: run.concern_version,
                      engine_version: run.engine_version,
                      sdk_version: run.sdk_version,
                      effective_parameters: run.effective_parameters,
                    },
                    null,
                    2,
                  )}
                </pre>
              ),
            },
          ]}
        />
      </Card>
    </section>
  );
}
