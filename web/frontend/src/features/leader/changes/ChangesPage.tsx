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
  Tag,
  Typography,
} from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { api, ApiError, unwrap } from "../../../api/client";
import type { components } from "../../../api/schema";
import { chooseEntry } from "../../../app/entry";
import { resourceKey, useResourceContext } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ErrorState, LoadingState } from "../../../components/States";
import { useNetworks, useSnapshots } from "../../networks/queries";
import { useCandidates } from "../../inventory/useCandidates";
import {
  prepareChangeCheck,
  prepareFaultCheck,
  relevantConcern,
  type ChangeDraft,
  type ChangeTemplateId,
} from "./model";

type Comparison = components["schemas"]["ComparisonDTO"];
type Concern = components["schemas"]["ConcernDTO"];
const short = (value: string) => value.slice(0, 8);
const ready = (value: string) =>
  value === "ready" || value === "ready_with_warnings";
const knownRejection = new Set([
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "NOT_READY",
  "CONFLICT",
  "FORBIDDEN",
  "RATE_LIMITED",
]);

function NetworkChoice({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (id: string) => void;
}) {
  const networks = useNetworks();
  const session = useSession();
  const selected = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: value, snapshotId: null },
      "leader-pinned-network",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}", {
          signal,
          params: { path: { network_id: value! } },
        }),
      ),
    enabled: !!value,
  });
  const rows = Array.from(
    new Map(
      [
        selected.data,
        ...(networks.data?.pages.flatMap((page) => page.items) ?? []),
      ]
        .filter((item) => !!item)
        .map((item) => [item!.id, item!]),
    ).values(),
  );
  return (
    <>
      <label className="leader-checks-field">
        网络
        <Select
          aria-label="变更网络"
          value={value}
          showSearch={{ optionFilterProp: "label" }}
          virtual={false}
          placeholder="选择共享网络"
          options={rows.map((item) => ({
            value: item.id,
            label: `${item.display_name} · ${short(item.id)}`,
            disabled: item.sync_state !== "ready",
          }))}
          onChange={onChange}
        />
      </label>
      {networks.hasNextPage && (
        <Button onClick={() => void networks.fetchNextPage()}>
          加载更多网络
        </Button>
      )}
      {networks.isError && (
        <ErrorState
          error={networks.error}
          retry={() => void networks.refetch()}
        />
      )}
      {selected.isError && (
        <ErrorState
          error={selected.error}
          retry={() => void selected.refetch()}
        />
      )}
    </>
  );
}

function SnapshotChoices({
  networkId,
  pinnedIds = [],
  children,
}: {
  networkId: string | null;
  pinnedIds?: (string | null)[];
  children: (
    items: components["schemas"]["SnapshotDTO"][],
    more: React.ReactNode,
  ) => React.ReactNode;
}) {
  const snapshots = useSnapshots(networkId);
  const [firstId, secondId] = pinnedIds;
  const session = useSession();
  const first = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: firstId ?? null },
      "leader-pinned-snapshot",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: { path: { network_id: networkId!, snapshot_id: firstId! } },
        }),
      ),
    enabled: !!networkId && !!firstId,
  });
  const second = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: secondId ?? null },
      "leader-pinned-snapshot",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: { path: { network_id: networkId!, snapshot_id: secondId! } },
        }),
      ),
    enabled: !!networkId && !!secondId,
  });
  const items = Array.from(
    new Map(
      [
        first.data,
        second.data,
        ...(snapshots.data?.pages.flatMap((page) => page.items) ?? []),
      ]
        .filter((item) => item && ready(item.status))
        .map((item) => [item!.id, item!]),
    ).values(),
  );
  return (
    <>
      {children(
        items,
        snapshots.hasNextPage ? (
          <Button onClick={() => void snapshots.fetchNextPage()}>
            加载更多快照
          </Button>
        ) : null,
      )}
      {snapshots.isError && (
        <ErrorState
          error={snapshots.error}
          retry={() => void snapshots.refetch()}
        />
      )}
      {first.isError && (
        <ErrorState error={first.error} retry={() => void first.refetch()} />
      )}
      {second.isError && (
        <ErrorState error={second.error} retry={() => void second.refetch()} />
      )}
    </>
  );
}

export function LeaderChangesPage() {
  const { comparisonId } = useParams();
  return comparisonId ? (
    <ComparisonDetail comparisonId={comparisonId} />
  ) : (
    <ChangeWorkspace />
  );
}

function ChangeWorkspace() {
  const session = useSession();
  const { network } = useResourceContext();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [networkId, setNetworkId] = useState<string | null>(
    search.get("network") ?? network?.id ?? null,
  );
  const [baselineId, setBaselineId] = useState<string | null>(
    search.get("baseline"),
  );
  const [candidateId, setCandidateId] = useState<string | null>(
    search.get("candidate"),
  );
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [offset, setOffset] = useState(0);
  const comparisons = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "leader-comparisons",
      { offset },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/comparisons", {
          signal,
          params: {
            path: { network_id: networkId! },
            query: { offset, limit: 20 },
          },
        }),
      ),
    enabled: !!networkId,
  });
  async function create() {
    if (
      !networkId ||
      !baselineId ||
      !candidateId ||
      baselineId === candidateId ||
      busy ||
      locked
    )
      return;
    setBusy(true);
    setError(null);
    try {
      const created = await unwrap(
        api.POST("/api/v1/networks/{network_id}/comparisons", {
          params: { path: { network_id: networkId } },
          body: {
            baseline_snapshot_id: baselineId,
            candidate_snapshot_id: candidateId,
          },
        }),
      );
      void client.invalidateQueries({
        queryKey: resourceKey(
          session?.user_id ?? null,
          { networkId, snapshotId: null },
          "leader-comparisons",
          { offset },
        ),
      });
      navigate(`/leader/changes/${created.id}`);
    } catch (caught) {
      setError(caught);
      if (
        !(
          caught instanceof ApiError &&
          [
            "VALIDATION_ERROR",
            "CONFLICT",
            "FORBIDDEN",
            "NOT_FOUND",
            "NOT_READY",
            "RATE_LIMITED",
          ].includes(caught.code)
        )
      )
        setLocked(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="leader-checks-page">
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">CHANGE STORY / 变更与故障</span>
          <Typography.Title level={1}>变更前后，哪里不同？</Typography.Title>
          <p>
            明确选择同一网络的两份就绪配置，固定左侧基线、右侧候选，再检查具体范围。
          </p>
        </div>
        <Link to="/leader/faults">
          模拟设备或接口故障 <ArrowRightOutlined />
        </Link>
      </div>
      <Card title="01 / 固定比较来源" className="leader-checks-panel">
        <NetworkChoice
          value={networkId}
          onChange={(value) => {
            setNetworkId(value);
            setBaselineId(null);
            setCandidateId(null);
            setOffset(0);
            setError(null);
          }}
        />
        <SnapshotChoices
          networkId={networkId}
          pinnedIds={[baselineId, candidateId]}
        >
          {(items, more) => (
            <>
              <div className="leader-checks-detail-grid">
                <label className="leader-checks-field">
                  左侧 · 基线快照
                  <Select
                    aria-label="左侧基线快照"
                    value={baselineId}
                    virtual={false}
                    showSearch={{ optionFilterProp: "label" }}
                    disabled={!networkId}
                    options={items.map((item) => ({
                      value: item.id,
                      label: `${item.display_name} · ${short(item.id)}`,
                      disabled: item.id === candidateId,
                    }))}
                    onChange={setBaselineId}
                  />
                </label>
                <label className="leader-checks-field">
                  右侧 · 候选快照
                  <Select
                    aria-label="右侧候选快照"
                    value={candidateId}
                    virtual={false}
                    showSearch={{ optionFilterProp: "label" }}
                    disabled={!networkId}
                    options={items.map((item) => ({
                      value: item.id,
                      label: `${item.display_name} · ${short(item.id)}`,
                      disabled: item.id === baselineId,
                    }))}
                    onChange={setCandidateId}
                  />
                </label>
              </div>
              {more}
              <div className="leader-checks-source">
                <strong>固定方向：基线（左） → 候选（右）</strong>
                <span>
                  比较记录创建后不会因页面选择变化而改写；原始快照保持不变。
                </span>
              </div>
              {baselineId && candidateId && baselineId === candidateId && (
                <Alert type="warning" title="基线与候选必须是不同快照。" />
              )}
              {items.some(
                (item) =>
                  item.id === baselineId &&
                  item.status === "ready_with_warnings",
              ) ||
              items.some(
                (item) =>
                  item.id === candidateId &&
                  item.status === "ready_with_warnings",
              ) ? (
                <Alert
                  type="warning"
                  title="至少一份快照带解析警告；比较结论需结合模型限制审阅。"
                />
              ) : null}
              <div className="leader-checks-actions">
                <span>只建立不可变比较关系，不自动推断业务影响。</span>
                <Button
                  type="primary"
                  loading={busy}
                  disabled={
                    !baselineId ||
                    !candidateId ||
                    baselineId === candidateId ||
                    locked
                  }
                  onClick={() => void create()}
                >
                  创建固定比较
                </Button>
              </div>
            </>
          )}
        </SnapshotChoices>
        {error !== null && <ErrorState error={error} />}
        {locked && (
          <Alert
            type="warning"
            title="创建结果暂不确定，请先刷新下方比较记录确认，避免重复创建。"
            action={
              <Button
                onClick={() => {
                  setLocked(false);
                  void comparisons.refetch();
                }}
              >
                刷新记录
              </Button>
            }
          />
        )}
      </Card>
      <Card title="02 / 最近的固定比较" className="leader-checks-panel">
        {comparisons.isError && (
          <ErrorState
            error={comparisons.error}
            retry={() => void comparisons.refetch()}
          />
        )}
        {comparisons.isPending ? (
          <LoadingState />
        ) : comparisons.data?.items.length ? (
          <div className="leader-checks-history">
            {comparisons.data.items.map((item) => (
              <Link key={item.id} to={`/leader/changes/${item.id}`}>
                <strong>{item.display_name}</strong>
                <span>
                  基线 {short(item.baseline_snapshot_id)} → 候选{" "}
                  {short(item.candidate_snapshot_id)} ·{" "}
                  {item.coverage === "complete" ? "覆盖完整" : "覆盖有限"}
                </span>
                <ArrowRightOutlined />
              </Link>
            ))}
          </div>
        ) : (
          <Empty
            description={networkId ? "此网络尚无比较记录" : "先选择网络"}
          />
        )}
        {comparisons.data &&
          comparisons.data.total > offset + comparisons.data.items.length && (
            <Button onClick={() => setOffset((value) => value + 20)}>
              加载更多比较
            </Button>
          )}
      </Card>
    </section>
  );
}

function ComparisonDetail({ comparisonId }: { comparisonId: string }) {
  const session = useSession();
  const navigate = useNavigate();
  const [template, setTemplate] = useState<ChangeTemplateId>("change-config");
  const [draft, setDraft] = useState<ChangeDraft>({
    comparison_id: comparisonId,
  });
  const [concernId, setConcernId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const flight = useRef(false);
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const comparison = useQuery({
    queryKey: ["leader-comparison", session?.user_id, comparisonId],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/comparisons/{comparison_id}", {
          signal,
          params: { path: { comparison_id: comparisonId } },
        }),
      ),
  });
  const fixed = comparison.data;
  const baseline = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      {
        networkId: fixed?.network_id ?? null,
        snapshotId: fixed?.baseline_snapshot_id ?? null,
      },
      "leader-comparison-source",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: {
            path: {
              network_id: fixed!.network_id,
              snapshot_id: fixed!.baseline_snapshot_id,
            },
          },
        }),
      ),
    enabled: !!fixed,
  });
  const candidate = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      {
        networkId: fixed?.network_id ?? null,
        snapshotId: fixed?.candidate_snapshot_id ?? null,
      },
      "leader-comparison-source",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: {
            path: {
              network_id: fixed!.network_id,
              snapshot_id: fixed!.candidate_snapshot_id,
            },
          },
        }),
      ),
    enabled: !!fixed,
  });
  const concerns = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: fixed?.network_id ?? null, snapshotId: null },
      "leader-change-concerns",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/business-concerns", {
          signal,
          params: {
            query: { network_id: fixed!.network_id, offset: 0, limit: 200 },
          },
        }),
      ),
    enabled: !!fixed && template === "change-reachability",
  });
  const selectedConcern = concerns.data?.items.find(
    (item) => item.id === concernId,
  );
  const exactConcern =
    selectedConcern &&
    relevantConcern(
      selectedConcern,
      draft.start_location ?? "",
      draft.destination_ips ?? "",
      draft.protocol,
      draft.destination_port,
      draft.source_ip,
    );
  const runs = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: fixed?.network_id ?? null, snapshotId: null },
      "leader-change-runs",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/leader/check-runs", {
          signal,
          params: {
            query: { network_id: fixed!.network_id, offset: 0, limit: 100 },
          },
        }),
      ),
    enabled: !!fixed,
  });
  const relatedRuns =
    runs.data?.items.filter(
      (item) => item.effective_parameters.comparison_id === comparisonId,
    ) ?? [];
  async function submit() {
    if (!fixed || flight.current) return;
    setValidation(null);
    setError(null);
    let prepared;
    try {
      prepared = prepareChangeCheck(template, draft);
    } catch (caught) {
      setValidation(
        caught instanceof Error ? caught.message : "请核对比较范围",
      );
      return;
    }
    const body = {
      template_id: template,
      network_id: fixed.network_id,
      snapshot_id: fixed.candidate_snapshot_id,
      scope: prepared.scope,
      options: prepared.options,
      ...(template === "change-reachability" && selectedConcern && exactConcern
        ? {
            concern_id: selectedConcern.id,
            concern_version: selectedConcern.version,
          }
        : {}),
    };
    const signature = JSON.stringify(body);
    if (attempt.current?.signature !== signature)
      attempt.current = { signature, key: crypto.randomUUID() };
    flight.current = true;
    setBusy(true);
    try {
      const run = await unwrap(
        api.POST("/api/v1/leader/check-runs", {
          params: { header: { "idempotency-key": attempt.current.key } },
          body,
        }),
      );
      navigate(`/leader/checks/${run.id}`);
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && knownRejection.has(caught.code)) {
        attempt.current = null;
        setLocked(false);
      } else setLocked(true);
    } finally {
      flight.current = false;
      setBusy(false);
    }
  }
  if (comparison.isPending) return <LoadingState />;
  if (comparison.isError)
    return (
      <ErrorState
        error={comparison.error}
        retry={() => void comparison.refetch()}
      />
    );
  if (!fixed) return null;
  return (
    <section className="leader-checks-page">
      <Link className="leader-back-link" to="/leader/changes">
        返回变更与故障
      </Link>
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">FIXED COMPARISON / 固定比较</span>
          <Typography.Title level={1}>{fixed.display_name}</Typography.Title>
          <p>比较编号 {fixed.id}</p>
        </div>
        <Tag color={fixed.coverage === "complete" ? "blue" : "gold"}>
          {fixed.coverage === "complete" ? "覆盖完整" : "覆盖有限"}
        </Tag>
      </div>
      <Card title="01 / 固定方向" className="leader-checks-panel">
        <div className="leader-checks-detail-grid">
          <div className="leader-change-side">
            <span>左侧 · 基线</span>
            <strong>
              {baseline.data?.display_name ?? short(fixed.baseline_snapshot_id)}
            </strong>
            <small>{fixed.baseline_snapshot_id}</small>
          </div>
          <div className="leader-change-side candidate">
            <span>右侧 · 候选</span>
            <strong>
              {candidate.data?.display_name ??
                short(fixed.candidate_snapshot_id)}
            </strong>
            <small>{fixed.candidate_snapshot_id}</small>
          </div>
        </div>
        <p className="leader-checks-note">
          候选相对基线的新增、消失或变化；本记录与快照内容和引擎版本绑定，页面切换不改写方向。
        </p>
        {fixed.coverage_notes.map((note) => (
          <Alert key={note} type="warning" title={note} />
        ))}
        {baseline.isError && (
          <ErrorState
            error={baseline.error}
            retry={() => void baseline.refetch()}
          />
        )}
        {candidate.isError && (
          <ErrorState
            error={candidate.error}
            retry={() => void candidate.refetch()}
          />
        )}
      </Card>
      <Card title="02 / 想比较什么？" className="leader-checks-panel">
        <div
          className="leader-checks-templates"
          role="group"
          aria-label="变更检查类型"
        >
          {(
            ["change-config", "change-routes", "change-reachability"] as const
          ).map((id) => (
            <button
              key={id}
              type="button"
              className={
                template === id
                  ? "leader-check-template selected"
                  : "leader-check-template"
              }
              aria-pressed={template === id}
              disabled={locked}
              onClick={() => {
                setTemplate(id);
                setDraft({ comparison_id: comparisonId });
                setConcernId(null);
                setValidation(null);
              }}
            >
              <span>
                {
                  {
                    "change-config": "配置文件变化",
                    "change-routes": "路由变化",
                    "change-reachability": "可达性变化",
                  }[id]
                }
              </span>
              <small>
                {
                  {
                    "change-config": "对比两份快照的配置文本。",
                    "change-routes": "只比较明确网段的模型路由。",
                    "change-reachability": "只比较明确起点与目的的样本。",
                  }[id]
                }
              </small>
            </button>
          ))}
        </div>
        {template === "change-routes" && (
          <label className="leader-checks-field">
            要比较的 IPv4 网段
            <Input
              aria-label="要比较的 IPv4 网段"
              value={draft.network ?? ""}
              disabled={locked}
              onChange={(event) =>
                setDraft({ ...draft, network: event.target.value })
              }
              placeholder="例如 10.64.0.0/24"
            />
          </label>
        )}
        {template === "change-reachability" && (
          <>
            <div className="leader-checks-fields">
              <label className="leader-checks-field">
                起点设备或接口
                <Input
                  aria-label="变更流量起点"
                  value={draft.start_location ?? ""}
                  disabled={locked}
                  onChange={(event) => {
                    setDraft({ ...draft, start_location: event.target.value });
                    setConcernId(null);
                  }}
                />
              </label>
              <label className="leader-checks-field">
                目的 IPv4 地址
                <Input
                  aria-label="变更流量目的"
                  value={draft.destination_ips ?? ""}
                  disabled={locked}
                  onChange={(event) => {
                    setDraft({ ...draft, destination_ips: event.target.value });
                    setConcernId(null);
                  }}
                />
              </label>
            </div>
            {concerns.data && concerns.data.items.length > 0 && (
              <label className="leader-checks-field">
                从业务关注项预填一条流量
                <Select
                  aria-label="变更业务关注项"
                  allowClear
                  virtual={false}
                  value={concernId}
                  disabled={locked}
                  options={concerns.data.items.map((item) => ({
                    value: item.id,
                    label: `${item.name} · 第 ${item.version} 版`,
                  }))}
                  onChange={(value) => {
                    const item = concerns.data?.items.find(
                      (entry) => entry.id === value,
                    );
                    const flow = item?.flows[0];
                    if (!item || !flow) {
                      setConcernId(null);
                      return;
                    }
                    setConcernId(item.id);
                    setDraft({
                      comparison_id: comparisonId,
                      start_location: flow.start_location,
                      destination_ips: flow.destination_ip,
                      source_ip: flow.source_ip ?? "",
                      protocol: flow.protocol ?? undefined,
                      destination_port: flow.destination_port ?? null,
                    });
                  }}
                />
              </label>
            )}
            {selectedConcern && (
              <Alert
                type="info"
                title={
                  exactConcern
                    ? `已绑定 ${selectedConcern.name} 第 ${selectedConcern.version} 版；仅说明本次流量与映射一致，不能推断业务受影响。`
                    : "流量条件已改变，当前业务关注项不再匹配；提交时不会绑定它。"
                }
              />
            )}
          </>
        )}
        {template !== "change-config" && (
          <Collapse
            className="leader-checks-advanced"
            destroyOnHidden={false}
            items={[
              {
                key: "advanced",
                label: "高级条件（折叠保值）",
                children: (
                  <div className="leader-checks-fields">
                    {template === "change-routes" && (
                      <label className="leader-checks-field">
                        只看这些设备（逗号分隔）
                        <Input
                          aria-label="变更范围设备"
                          value={draft.nodes ?? ""}
                          disabled={locked}
                          onChange={(event) =>
                            setDraft({ ...draft, nodes: event.target.value })
                          }
                        />
                      </label>
                    )}
                    {template === "change-reachability" && (
                      <>
                        <label className="leader-checks-field">
                          源 IPv4 地址
                          <Input
                            aria-label="变更源地址"
                            value={draft.source_ip ?? ""}
                            disabled={locked}
                            onChange={(event) =>
                              setDraft({
                                ...draft,
                                source_ip: event.target.value,
                              })
                            }
                          />
                        </label>
                        <label className="leader-checks-field">
                          协议
                          <Select
                            aria-label="变更协议"
                            value={draft.protocol ?? "icmp"}
                            disabled={locked}
                            virtual={false}
                            options={["icmp", "tcp", "udp"].map((value) => ({
                              value,
                              label: value.toUpperCase(),
                            }))}
                            onChange={(value) =>
                              setDraft({
                                ...draft,
                                protocol: value,
                                destination_port: null,
                              })
                            }
                          />
                        </label>
                        {(draft.protocol === "tcp" ||
                          draft.protocol === "udp") && (
                          <label className="leader-checks-field">
                            目标端口
                            <InputNumber
                              aria-label="变更目标端口"
                              min={0}
                              max={65535}
                              value={draft.destination_port ?? null}
                              disabled={locked}
                              onChange={(value) =>
                                setDraft({ ...draft, destination_port: value })
                              }
                            />
                          </label>
                        )}
                        <label className="leader-checks-field">
                          最多保存路径
                          <InputNumber
                            aria-label="变更最多路径"
                            min={1}
                            max={20}
                            value={draft.max_traces ?? null}
                            disabled={locked}
                            onChange={(value) =>
                              setDraft({ ...draft, max_traces: value })
                            }
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
          <span>只运行选中的检查；未检查项目保持未知。</span>
          <Button type="primary" loading={busy} onClick={() => void submit()}>
            开始比较检查
          </Button>
        </div>
        {validation && <Alert type="warning" title={validation} />}
        {locked && (
          <Alert
            type="warning"
            title="提交结果暂不确定；条件已锁定。请按原条件重试，或从下方运行记录核对。"
          />
        )}
        {error !== null && (
          <ErrorState error={error} retry={() => void submit()} />
        )}
      </Card>
      <Card title="03 / 已保存的比较检查" className="leader-checks-panel">
        {runs.isError && (
          <ErrorState error={runs.error} retry={() => void runs.refetch()} />
        )}
        {runs.isPending ? (
          <LoadingState />
        ) : relatedRuns.length ? (
          <div className="leader-checks-history">
            {relatedRuns.map((item) => (
              <Link key={item.id} to={`/leader/checks/${item.id}`}>
                <strong>{item.template_id}</strong>
                <span>
                  {item.status} · {short(item.snapshot_id)}
                </span>
                <ArrowRightOutlined />
              </Link>
            ))}
          </div>
        ) : (
          <Empty description="尚未分析具体范围" />
        )}
      </Card>
      <Link to="/changes" onClick={() => chooseEntry("technical")}>
        进入技术工作台查看完整比较参数与原始结果 <ArrowRightOutlined />
      </Link>
    </section>
  );
}

export function LeaderFaultPage() {
  const { network, snapshot } = useResourceContext();
  const [networkId, setNetworkId] = useState<string | null>(
    network?.id ?? null,
  );
  const [snapshotId, setSnapshotId] = useState<string | null>(
    snapshot?.id ?? null,
  );
  return (
    <section className="leader-checks-page">
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">FAULT SCENARIO / 故障模拟</span>
          <Typography.Title level={1}>
            如果一个设备停用，会怎样？
          </Typography.Title>
          <p>
            仅在配置模型中生成派生快照，不操作真实设备；等待派生就绪后再检查明确的变化范围。
          </p>
        </div>
        <Link to="/leader/changes">
          返回固定比较 <ArrowRightOutlined />
        </Link>
      </div>
      <Card title="01 / 选择原始基线" className="leader-checks-panel">
        <NetworkChoice
          value={networkId}
          onChange={(value) => {
            setNetworkId(value);
            setSnapshotId(null);
          }}
        />
        <SnapshotChoices networkId={networkId} pinnedIds={[snapshotId]}>
          {(items, more) => (
            <>
              <label className="leader-checks-field">
                原始基线快照
                <Select
                  aria-label="故障基线快照"
                  value={snapshotId}
                  disabled={!networkId}
                  virtual={false}
                  showSearch={{ optionFilterProp: "label" }}
                  options={items.map((item) => ({
                    value: item.id,
                    label: `${item.display_name} · ${short(item.id)}`,
                  }))}
                  onChange={setSnapshotId}
                />
              </label>
              {more}
            </>
          )}
        </SnapshotChoices>
      </Card>
      {networkId && snapshotId ? (
        <FaultComposer
          key={`${networkId}:${snapshotId}`}
          networkId={networkId}
          snapshotId={snapshotId}
        />
      ) : (
        <Card>
          <Empty description="先选择网络和就绪基线" />
        </Card>
      )}
    </section>
  );
}

function FaultComposer({
  networkId,
  snapshotId,
}: {
  networkId: string;
  snapshotId: string;
}) {
  const navigate = useNavigate();
  const candidates = useCandidates(networkId, snapshotId);
  const [name, setName] = useState("");
  const [nodes, setNodes] = useState<string[]>([]);
  const [interfaceNode, setInterfaceNode] = useState<string | null>(null);
  const [interfaceName, setInterfaceName] = useState<string | null>(null);
  const [interfaces, setInterfaces] = useState<
    { node: string; interface: string }[]
  >([]);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const flight = useRef(false);
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  async function submit() {
    if (flight.current) return;
    setValidation(null);
    setError(null);
    let prepared;
    try {
      prepared = prepareFaultCheck({
        display_name: name,
        nodes: nodes.join(","),
        interfaces,
      });
    } catch (caught) {
      setValidation(
        caught instanceof Error ? caught.message : "请核对故障范围",
      );
      return;
    }
    const body = {
      template_id: "fault",
      network_id: networkId,
      snapshot_id: snapshotId,
      scope: prepared.scope,
      options: prepared.options,
    };
    const signature = JSON.stringify(body);
    if (attempt.current?.signature !== signature)
      attempt.current = { signature, key: crypto.randomUUID() };
    flight.current = true;
    setBusy(true);
    try {
      const run = await unwrap(
        api.POST("/api/v1/leader/check-runs", {
          params: { header: { "idempotency-key": attempt.current.key } },
          body,
        }),
      );
      navigate(`/leader/checks/${run.id}`);
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && knownRejection.has(caught.code)) {
        attempt.current = null;
        setLocked(false);
      } else setLocked(true);
    } finally {
      flight.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <Card title="02 / 选择要停用的对象" className="leader-checks-panel">
        <p className="leader-checks-note">
          先加载配置中识别出的设备与接口；仅选中的对象会进入方案。
        </p>
        {candidates.controls}
        <label className="leader-checks-field">
          停用设备
          <Select
            aria-label="故障停用设备"
            mode="multiple"
            virtual={false}
            showSearch={{ optionFilterProp: "label" }}
            value={nodes}
            disabled={locked}
            options={candidates.nodes.map((item) => ({
              value: item,
              label: item,
            }))}
            onChange={(value) => {
              setNodes(value);
              setInterfaces((old) =>
                old.filter((item) => !value.includes(item.node)),
              );
            }}
          />
        </label>
        <Collapse
          items={[
            {
              key: "interfaces",
              label: `也可停用接口（已选 ${interfaces.length} 个）`,
              children: (
                <>
                  <div className="leader-checks-fields">
                    <label className="leader-checks-field">
                      接口所属设备
                      <Select
                        aria-label="故障接口设备"
                        value={interfaceNode}
                        disabled={locked}
                        virtual={false}
                        options={candidates.nodes.map((item) => ({
                          value: item,
                          label: item,
                        }))}
                        onChange={(value) => {
                          setInterfaceNode(value);
                          setInterfaceName(null);
                        }}
                      />
                    </label>
                    <label className="leader-checks-field">
                      接口名称
                      <Select
                        aria-label="故障接口名称"
                        value={interfaceName}
                        disabled={locked || !interfaceNode}
                        virtual={false}
                        options={candidates
                          .interfaces(interfaceNode ? [interfaceNode] : [])
                          .map((item) => ({ value: item, label: item }))}
                        onChange={setInterfaceName}
                      />
                    </label>
                  </div>
                  <Button
                    disabled={
                      !interfaceNode ||
                      !interfaceName ||
                      locked ||
                      nodes.includes(interfaceNode)
                    }
                    onClick={() => {
                      if (
                        interfaceNode &&
                        interfaceName &&
                        !interfaces.some(
                          (item) =>
                            item.node === interfaceNode &&
                            item.interface === interfaceName,
                        )
                      )
                        setInterfaces([
                          ...interfaces,
                          { node: interfaceNode, interface: interfaceName },
                        ]);
                      setInterfaceName(null);
                    }}
                  >
                    加入接口
                  </Button>
                  <div className="leader-graph-nodes">
                    {interfaces.map((item) => (
                      <Tag
                        key={`${item.node}:${item.interface}`}
                        closable={!locked}
                        onClose={() =>
                          setInterfaces((old) =>
                            old.filter(
                              (entry) =>
                                entry.node !== item.node ||
                                entry.interface !== item.interface,
                            ),
                          )
                        }
                      >
                        {item.node} / {item.interface}
                      </Tag>
                    ))}
                  </div>
                </>
              ),
            },
          ]}
        />
      </Card>
      <Card title="03 / 确认派生关系" className="leader-checks-panel">
        <div className="leader-checks-detail-grid">
          <div className="leader-change-side">
            <span>原始基线</span>
            <strong>{short(snapshotId)}</strong>
            <small>保持不变</small>
          </div>
          <div className="leader-change-side candidate">
            <span>派生候选</span>
            <strong>{name.trim() || "待命名方案"}</strong>
            <small>
              停用 {nodes.length} 台设备、{interfaces.length} 个接口
            </small>
          </div>
        </div>
        <Alert
          type="info"
          title="仅生成新的模型快照；不会修改原始配置，也不会操作真实设备。"
        />
        <label className="leader-checks-field">
          方案名称
          <Input
            aria-label="故障方案名称"
            value={name}
            disabled={locked}
            onChange={(event) => setName(event.target.value)}
            placeholder="例如：模拟 c2 停用"
          />
        </label>
        {validation && <Alert type="warning" title={validation} />}
        {locked && (
          <Alert
            type="warning"
            title="提交结果暂不确定；方案内容已锁定。请按原条件重试，以同一请求编号核对结果。"
          />
        )}
        {error !== null && (
          <ErrorState error={error} retry={() => void submit()} />
        )}
        <div className="leader-checks-actions">
          <span>提交后可离开，运行记录会保留进度。</span>
          <Button type="primary" loading={busy} onClick={() => void submit()}>
            创建派生快照
          </Button>
        </div>
      </Card>
    </>
  );
}
