import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Empty,
  Input,
  Modal,
  Select,
  Space,
  Steps,
  Switch,
  Tag,
  Typography,
} from "antd";
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  ExpandOutlined,
  LinkOutlined,
  PrinterOutlined,
} from "@ant-design/icons";
import {
  useInfiniteQuery,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, unwrap } from "../../../api/client";
import type { components } from "../../../api/schema";
import { chooseEntry } from "../../../app/entry";
import { resourceKey, useResourceContext } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ThemeControl } from "../../../app/theme";
import { ErrorState, LoadingState } from "../../../components/States";
import { useNetworks, useSnapshots } from "../../networks/queries";
import {
  briefingIndicators,
  readableWarning,
  reportableRuns,
  selectedSources,
  summaryFacts,
} from "./model";

type Briefing = components["schemas"]["Briefing"];
type Section = components["schemas"]["BriefingSection"];
const ready = (status: string) =>
  status === "ready" || status === "ready_with_warnings";
const knownRejection = new Set([
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "NOT_READY",
  "CONFLICT",
  "FORBIDDEN",
  "RATE_LIMITED",
]);
const short = (value: string) => value.slice(0, 8);
const when = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
const templateNames: Record<string, string> = {
  "configuration-quality": "配置质量",
  devices: "设备",
  interfaces: "接口",
  routes: "路由",
  "lpm-routes": "最长前缀匹配",
  traceroute: "单向连通性",
  topology: "拓扑关系",
  bgp: "BGP",
  acl: "ACL",
  "change-config": "配置变化",
  "change-routes": "路由变化",
  "change-reachability": "可达性变化",
};

function reportKey(userId: string | undefined, id: string) {
  return resourceKey(
    userId ?? null,
    { networkId: null, snapshotId: null },
    "leader-briefing",
    { id },
  );
}

function useBriefing(id: string) {
  const session = useSession();
  return useQuery({
    queryKey: reportKey(session?.user_id, id),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/leader/briefings/{briefing_id}", {
          signal,
          params: { path: { briefing_id: id } },
        }),
      ),
  });
}

function BriefingVisual({ section }: { section: Section }) {
  const facts = summaryFacts(section.summary);
  const counts = ["added", "removed", "changed"] as const;
  const changeCounts = counts.map((key) => ({
    key,
    value:
      typeof section.summary[key] === "number"
        ? Math.max(0, Number(section.summary[key]))
        : 0,
  }));
  const total = changeCounts.reduce((sum, item) => sum + item.value, 0);
  return (
    <>
      <div className="leader-briefing-metrics">
        {facts.length ? (
          facts.map((fact) => (
            <div key={`${fact.label}:${fact.value}`}>
              <strong>{fact.value}</strong>
              <span>{fact.label}</span>
            </div>
          ))
        ) : (
          <p>当前结果没有可汇总的数量；可按来源查看完整证据。</p>
        )}
      </div>
      {total > 0 && (
        <div className="leader-briefing-bars" aria-label="固定差异数量图">
          {changeCounts.map(({ key, value }) => (
            <div key={key} className={`leader-briefing-bar ${key}`}>
              <span>
                {{ added: "新增", removed: "消失", changed: "变化" }[key]}
              </span>
              <div aria-hidden="true">
                <i style={{ width: `${(value / total) * 100}%` }} />
              </div>
              <b>{value}</b>
            </div>
          ))}
          <small>仅表示当前固定结果中的数量，不代表全网影响。</small>
        </div>
      )}
    </>
  );
}

function SectionCard({
  section,
  index,
  meeting = false,
}: {
  section: Section;
  index: number;
  meeting?: boolean;
}) {
  const indicators = briefingIndicators(section);
  return (
    <article
      className={
        meeting ? "leader-briefing-section meeting" : "leader-briefing-section"
      }
    >
      <div className="leader-briefing-section-head">
        <div>
          <span className="leader-kicker">
            EVIDENCE {String(index + 1).padStart(2, "0")}
          </span>
          <h2>
            {section.kind === "graph"
              ? "拓扑关系"
              : section.kind === "diff"
                ? "配置变化"
                : section.kind === "traces"
                  ? "路径推演"
                  : "模型检查"}
          </h2>
          <p>固定结果 {section.result_id}</p>
        </div>
        <Tag color={section.coverage === "complete" ? "blue" : "gold"}>
          {section.coverage === "complete" ? "覆盖完整" : "覆盖有限或未知"}
        </Tag>
      </div>
      <BriefingVisual section={section} />
      {indicators.length > 0 && (
        <div className="leader-briefing-warnings">
          {indicators.map((item, warningIndex) => (
            <p key={`${warningIndex}:${item}`}>{item}</p>
          ))}
        </div>
      )}
      <div className="leader-briefing-section-foot">
        <span>
          引擎 {section.engine_version} · SDK {section.sdk_version} · 生成于{" "}
          {when(section.created_at)}
        </span>
        {section.evidence_available ? (
          <Link
            to={`/results/${section.result_id}`}
            onClick={() => chooseEntry("technical")}
            className="leader-briefing-evidence-link"
          >
            查看原始证据 <ArrowRightOutlined />
          </Link>
        ) : (
          <span className="leader-briefing-unavailable">
            来源已不可用 · {section.result_id}
          </span>
        )}
      </div>
      {!meeting && (
        <Collapse
          className="leader-briefing-scope"
          items={[
            {
              key: "scope",
              label: "查看本节生效范围与参数",
              children: (
                <pre>
                  {JSON.stringify(section.effective_parameters, null, 2)}
                </pre>
              ),
            },
          ]}
        />
      )}
    </article>
  );
}

function ReportFacts({
  report,
  meeting = false,
}: {
  report: Briefing;
  meeting?: boolean;
}) {
  const comparison = report.frozen_comparison;
  const baseline = comparison?.baseline_snapshot_id;
  const concernName = report.frozen_concern?.name;
  const visibleWarnings = report.warnings
    .filter((warning) => !warning.startsWith("{'vendor':"))
    .slice(0, 3);
  const hasMoreWarnings = report.warnings.length > visibleWarnings.length;
  return (
    <>
      <div className="leader-briefing-source">
        <div>
          <span>网络</span>
          <strong>{report.network_name}</strong>
          <small>{report.network_id}</small>
        </div>
        <div>
          <span>固定快照</span>
          <strong>{report.snapshot_name}</strong>
          <small>{report.snapshot_id}</small>
        </div>
        <div>
          <span>报告版本</span>
          <strong>第 {report.version} 版</strong>
          <small>{when(report.created_at)}</small>
        </div>
      </div>
      {comparison && (
        <Alert
          type="info"
          title={`固定比较：基线 ${typeof baseline === "string" ? short(baseline) : "—"} → 候选 ${short(report.snapshot_id)}`}
          description={`比较编号 ${report.comparison_id}`}
        />
      )}
      {typeof concernName === "string" && (
        <Alert
          type="info"
          title={`业务关注项：${concernName} · 第 ${report.concern_version} 版`}
          description="此处只保存当时选定的映射，不自动认定业务受影响。"
        />
      )}
      {!report.source_available && (
        <Alert
          type="warning"
          title="原网络、快照或比较来源已不可用；以下固定事实仍保留，原始证据链接已关闭。"
        />
      )}
      <div className="leader-briefing-caveat">
        <strong>模型边界</strong>
        <p>
          结论基于当时的配置快照和 Batfish
          模型；未检查的范围保持未知，不代表现场设备状态。
        </p>
        {visibleWarnings.length > 0 && (
          <ul className="leader-briefing-screen-warnings">
            {visibleWarnings.map((warning, index) => (
              <li key={`${index}:${warning}`}>{readableWarning(warning)}</li>
            ))}
          </ul>
        )}
        {hasMoreWarnings && (
          <details className="leader-briefing-warning-details">
            <summary>
              查看全部 {report.warnings.length} 条固定模型限制与警告
            </summary>
            <ul>
              {report.warnings.map((warning, index) => (
                <li key={`${index}:${warning}`}>{readableWarning(warning)}</li>
              ))}
            </ul>
          </details>
        )}
        {report.warnings.length > 0 && (
          <ul className="leader-briefing-print-warnings">
            {report.warnings.map((warning, index) => (
              <li key={`${index}:${warning}`}>{readableWarning(warning)}</li>
            ))}
          </ul>
        )}
        {!report.warnings.length && (
          <span>该报告没有额外模型警告；仍须按固定范围解读。</span>
        )}
      </div>
      <div className="leader-briefing-section-list">
        {report.sections.map((section, index) => (
          <SectionCard
            key={section.result_id}
            section={section}
            index={index}
            meeting={meeting}
          />
        ))}
      </div>
      {report.notes && (
        <aside className="leader-briefing-notes">
          <span>人工备注 · 由团队填写</span>
          <p>{report.notes}</p>
        </aside>
      )}
    </>
  );
}

function BriefingList() {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const [includeArchived, setIncludeArchived] = useState(false);
  const list = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: null, snapshotId: null },
      "leader-briefings",
      { offset, includeArchived },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/leader/briefings", {
          signal,
          params: {
            query: { offset, limit: 20, include_archived: includeArchived },
          },
        }),
      ),
  });
  return (
    <section className="leader-briefings-page">
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">FIXED REPORTS / 固定汇报</span>
          <Typography.Title level={1}>让每次汇报都有出处</Typography.Title>
          <p>
            报告保存创建时的范围、事实与限制；后续检查和映射修改不会改写旧版。
          </p>
        </div>
        <Link className="leader-briefing-cta" to="/leader/briefings/new">
          创建固定汇报 <ArrowRightOutlined />
        </Link>
      </div>
      <div className="leader-briefing-list-head">
        <span>团队内共享 · {list.data?.total ?? "—"} 份汇报</span>
        <label>
          包含已归档{" "}
          <Switch
            checked={includeArchived}
            onChange={(value) => {
              setIncludeArchived(value);
              setOffset(0);
            }}
          />
        </label>
      </div>
      {list.isPending && <LoadingState />}
      {list.isError && (
        <ErrorState error={list.error} retry={() => void list.refetch()} />
      )}
      {list.data &&
        (list.data.items.length ? (
          <div className="leader-briefing-list">
            {list.data.items.map((item) => (
              <Link key={item.id} to={`/leader/briefings/${item.id}`}>
                <div>
                  <span className="leader-kicker">
                    REPORT · V{item.version}
                  </span>
                  <strong>{item.title}</strong>
                  <p>
                    {item.network_name} / {item.snapshot_name}
                  </p>
                </div>
                <div className="leader-briefing-list-meta">
                  {item.archived && <Tag>已归档</Tag>}
                  <span>{item.sections.length} 节证据</span>
                  <span>{when(item.created_at)}</span>
                  <ArrowRightOutlined />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <Card>
            <Empty description="还没有固定汇报；先完成检查，再选择结果生成汇报。" />
          </Card>
        ))}
      {list.data && list.data.total > 20 && (
        <Space className="leader-briefing-pagination">
          <Button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            上一页
          </Button>
          <span>第 {offset / 20 + 1} 页</span>
          <Button
            disabled={offset + 20 >= list.data.total}
            onClick={() => setOffset(offset + 20)}
          >
            下一页
          </Button>
        </Space>
      )}
    </section>
  );
}

function BriefingCreate() {
  const session = useSession();
  const navigate = useNavigate();
  const { network: selectedNetwork } = useResourceContext();
  const networks = useNetworks();
  const [networkId, setNetworkId] = useState<string | null>(
    selectedNetwork?.id ?? null,
  );
  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  const snapshots = useSnapshots(networkId);
  const pinnedNetwork = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "leader-briefing-network",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}", {
          signal,
          params: { path: { network_id: networkId! } },
        }),
      ),
    enabled: !!networkId,
  });
  const pinnedSnapshot = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId },
      "leader-briefing-snapshot",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
          signal,
          params: {
            path: { network_id: networkId!, snapshot_id: snapshotId! },
          },
        }),
      ),
    enabled: !!networkId && !!snapshotId,
  });
  const networkItems = Array.from(
    new Map(
      [
        pinnedNetwork.data,
        ...(networks.data?.pages.flatMap((page) => page.items) ?? []),
      ]
        .filter((item) => !!item)
        .map((item) => [item!.id, item!]),
    ).values(),
  );
  const snapshotItems = Array.from(
    new Map(
      [
        pinnedSnapshot.data,
        ...(snapshots.data?.pages.flatMap((page) => page.items) ?? []),
      ]
        .filter((item) => item && ready(item.status))
        .map((item) => [item!.id, item!]),
    ).values(),
  );
  const runs = useInfiniteQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "leader-briefing-runs",
    ),
    queryFn: ({ pageParam, signal }) =>
      unwrap(
        api.GET("/api/v1/leader/check-runs", {
          signal,
          params: {
            query: { network_id: networkId!, offset: pageParam, limit: 100 },
          },
        }),
      ),
    initialPageParam: 0,
    getNextPageParam: (page) =>
      page.offset + page.items.length < page.total
        ? page.offset + page.items.length
        : undefined,
    enabled: !!networkId && !!snapshotId,
  });
  const candidates = reportableRuns(
    runs.data?.pages.flatMap((page) => page.items) ?? [],
    snapshotId ?? "",
  );
  const selectedRuns = candidates.filter((item) =>
    selectedIds.includes(item.id),
  );
  let sources: ReturnType<typeof selectedSources> | null = null;
  let selectionError: string | null = null;
  if (selectedRuns.length) {
    try {
      sources = selectedSources(selectedRuns);
    } catch (cause) {
      selectionError = cause instanceof Error ? cause.message : "检查选择无效";
    }
  }
  const resultIds = sources?.resultIds ?? [];
  const previews = useQueries({
    queries: resultIds.map((id) => ({
      queryKey: resourceKey(
        session?.user_id ?? null,
        { networkId, snapshotId },
        "leader-briefing-preview",
        {},
        id,
      ),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        unwrap(
          api.GET("/api/v1/results/{result_id}", {
            signal,
            params: { path: { result_id: id } },
          }),
        ),
    })),
  });
  const previewReady =
    resultIds.length > 0 && previews.every((item) => item.isSuccess);
  const step = !networkId || !snapshotId ? 0 : !selectedIds.length ? 1 : 2;

  async function submit() {
    if (
      busy ||
      !networkId ||
      !snapshotId ||
      !sources ||
      !previewReady ||
      !title.trim()
    )
      return;
    setError(null);
    setValidation(null);
    const body = {
      title: title.trim(),
      network_id: networkId,
      snapshot_id: snapshotId,
      result_ids: sources.resultIds,
      ...(sources.comparisonId ? { comparison_id: sources.comparisonId } : {}),
      ...(sources.concernId && sources.concernVersion
        ? {
            concern_id: sources.concernId,
            concern_version: sources.concernVersion,
          }
        : {}),
      notes: notes.trim() || null,
    };
    const signature = JSON.stringify(body);
    if (attempt.current?.signature !== signature)
      attempt.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    try {
      const report = await unwrap(
        api.POST("/api/v1/leader/briefings", {
          params: { header: { "idempotency-key": attempt.current.key } },
          body,
        }),
      );
      navigate(`/leader/briefings/${report.id}`);
    } catch (cause) {
      setError(cause);
      if (cause instanceof ApiError && knownRejection.has(cause.code)) {
        attempt.current = null;
        setLocked(false);
      } else setLocked(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="leader-briefings-page">
      <Link className="leader-back-link" to="/leader/briefings">
        <ArrowLeftOutlined /> 返回汇报列表
      </Link>
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">REPORT BUILDER / 创建汇报</span>
          <Typography.Title level={1}>
            从已完成的检查，形成固定汇报
          </Typography.Title>
          <p>选择网络、快照及明确的检查结果；未检查的内容不进入汇报。</p>
        </div>
      </div>
      <Steps
        className="leader-briefing-steps"
        current={step}
        items={[
          { title: "确定来源" },
          { title: "选择证据" },
          { title: "确认并固定" },
        ]}
      />
      <Card title="01 / 确定网络与快照" className="leader-checks-panel">
        <div className="leader-checks-fields">
          <label className="leader-checks-field">
            共享网络
            <Select
              aria-label="汇报网络"
              virtual={false}
              showSearch={{ optionFilterProp: "label" }}
              disabled={locked}
              value={networkId}
              options={networkItems.map((item) => ({
                value: item.id,
                label: `${item.display_name} · ${short(item.id)}`,
                disabled: item.sync_state !== "ready",
              }))}
              onChange={(value) => {
                setNetworkId(value);
                setSnapshotId(null);
                setSelectedIds([]);
                setTitle("");
              }}
            />
          </label>
          <label className="leader-checks-field">
            固定快照
            <Select
              aria-label="汇报快照"
              virtual={false}
              showSearch={{ optionFilterProp: "label" }}
              disabled={!networkId || locked}
              value={snapshotId}
              options={snapshotItems.map((item) => ({
                value: item.id,
                label: `${item.display_name} · ${short(item.id)}`,
              }))}
              onChange={(value) => {
                setSnapshotId(value);
                setSelectedIds([]);
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
        {pinnedNetwork.isError && (
          <ErrorState
            error={pinnedNetwork.error}
            retry={() => void pinnedNetwork.refetch()}
          />
        )}
        {snapshots.isError && (
          <ErrorState
            error={snapshots.error}
            retry={() => void snapshots.refetch()}
          />
        )}
        {pinnedSnapshot.isError && (
          <ErrorState
            error={pinnedSnapshot.error}
            retry={() => void pinnedSnapshot.refetch()}
          />
        )}
      </Card>
      <Card title="02 / 选择已完成的检查" className="leader-checks-panel">
        <p className="leader-checks-note">
          只能选择当前快照的已完成结果；不同的固定比较不能混合。
        </p>
        {runs.isPending && snapshotId && <LoadingState />}
        {runs.isError && (
          <ErrorState error={runs.error} retry={() => void runs.refetch()} />
        )}
        {snapshotId && !runs.isPending && !candidates.length && (
          <Empty description="此快照还没有可用于汇报的结果，请先完成自主检查。" />
        )}
        <div className="leader-briefing-run-list">
          {candidates.map((item) => (
            <label key={item.id} className="leader-briefing-run">
              <Checkbox
                disabled={locked}
                checked={selectedIds.includes(item.id)}
                onChange={(event) =>
                  setSelectedIds((old) =>
                    event.target.checked
                      ? [...old, item.id]
                      : old.filter((id) => id !== item.id),
                  )
                }
              />
              <span>
                <strong>
                  {templateNames[item.template_id] ?? item.template_id}
                </strong>
                <small>
                  运行 {short(item.id)} · {item.result_ids.length} 个固定结果
                </small>
              </span>
            </label>
          ))}
        </div>
        {runs.hasNextPage && (
          <Button onClick={() => void runs.fetchNextPage()}>
            加载更多检查
          </Button>
        )}
        {selectionError && <Alert type="warning" title={selectionError} />}
      </Card>
      <Card title="03 / 确认固定事实与人工内容" className="leader-checks-panel">
        {resultIds.length > 0 && (
          <div className="leader-briefing-preview">
            {previews.map((item, index) => (
              <div key={resultIds[index]}>
                <strong>结果 {short(resultIds[index])}</strong>
                {item.isPending && <span>读取事实中…</span>}
                {item.isError && (
                  <ErrorState
                    error={item.error}
                    retry={() => void item.refetch()}
                  />
                )}
                {item.data && (
                  <>
                    <span>
                      模型覆盖 {item.data.coverage} ·{" "}
                      {item.data.truncated ? "已截断" : "未截断"}
                    </span>
                    <span>
                      {summaryFacts(item.data.summary)
                        .map((fact) => `${fact.label} ${fact.value}`)
                        .join(" · ") || "无可汇总数量"}
                    </span>
                    {item.data.warnings.map((warning, warningIndex) => (
                      <small key={`${warningIndex}:${warning}`}>
                        {warning}
                      </small>
                    ))}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
        <Alert
          type="info"
          title="以上为系统生成的固定事实；标题与备注是人工内容，单独标识。"
        />
        <label className="leader-checks-field">
          汇报标题
          <Input
            aria-label="汇报标题"
            disabled={locked}
            maxLength={200}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：本周核心网络检查"
          />
        </label>
        <label className="leader-checks-field">
          人工备注（可选）
          <Input.TextArea
            aria-label="汇报人工备注"
            disabled={locked}
            maxLength={4000}
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="仅填写人工观察或后续行动，不修改系统事实"
          />
        </label>
        {sources?.concernId && (
          <Alert
            type="info"
            title={`将固定业务关注项第 ${sources.concernVersion} 版；此映射本身不代表业务受影响。`}
          />
        )}
        {locked && (
          <Alert
            type="warning"
            title="提交结果暂不确定；内容已锁定。请按原条件重试，以同一请求编号核对结果。"
          />
        )}
        {validation && <Alert type="warning" title={validation} />}
        {error !== null && (
          <ErrorState error={error} retry={() => void submit()} />
        )}
        <div className="leader-checks-actions">
          <span>创建后固定事实不会因新检查或映射更新而改变。</span>
          <Button
            type="primary"
            loading={busy}
            disabled={
              !title.trim() || !sources || !previewReady || !!selectionError
            }
            onClick={() => void submit()}
          >
            生成固定汇报
          </Button>
        </div>
      </Card>
    </section>
  );
}

function BriefingDetail({ id }: { id: string }) {
  const report = useBriefing(id);
  const session = useSession();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [editError, setEditError] = useState<unknown>(null);
  const [archiveError, setArchiveError] = useState<unknown>(null);
  const [locked, setLocked] = useState(false);
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  if (report.isPending) return <LoadingState />;
  if (report.isError)
    return (
      <ErrorState error={report.error} retry={() => void report.refetch()} />
    );
  if (!report.data) return null;
  const fixed = report.data;
  function startEditing() {
    setTitle(fixed.title);
    setNotes(fixed.notes ?? "");
    setEditError(null);
    setEditing(true);
  }
  async function save() {
    if (busy || !title.trim() || (locked && !attempt.current)) return;
    const body = {
      expected_version: fixed.version,
      title: title.trim(),
      notes: notes.trim() || null,
    };
    const signature = JSON.stringify(body);
    if (attempt.current?.signature !== signature)
      attempt.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setEditError(null);
    try {
      const revised = await unwrap(
        api.PATCH("/api/v1/leader/briefings/{briefing_id}", {
          params: {
            path: { briefing_id: id },
            header: { "idempotency-key": attempt.current.key },
          },
          body,
        }),
      );
      void client.invalidateQueries({
        queryKey: ["resource", session?.user_id],
      });
      navigate(`/leader/briefings/${revised.id}?previous=${id}`);
    } catch (cause) {
      setEditError(cause);
      if (cause instanceof ApiError && knownRejection.has(cause.code)) {
        attempt.current = null;
        setLocked(false);
      } else setLocked(true);
    } finally {
      setBusy(false);
    }
  }
  async function archive() {
    setBusy(true);
    setArchiveError(null);
    try {
      await unwrap(
        api.POST("/api/v1/leader/briefings/{briefing_id}/archive", {
          params: { path: { briefing_id: id } },
        }),
      );
      void client.invalidateQueries({
        queryKey: ["resource", session?.user_id],
      });
      await report.refetch();
    } catch (cause) {
      setArchiveError(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="leader-briefings-page">
      <Link className="leader-back-link" to="/leader/briefings">
        <ArrowLeftOutlined /> 返回汇报列表
      </Link>
      <div className="leader-page-heading leader-briefing-detail-head">
        <div>
          <span className="leader-kicker">FIXED VERSION / 固定版本</span>
          <Typography.Title level={1}>{fixed.title}</Typography.Title>
          <p>
            报告 {fixed.report_id} · 当前修订 {fixed.id}
          </p>
        </div>
        <Space wrap>
          {fixed.archived && <Tag>已归档</Tag>}
          <Button onClick={() => void report.refetch()}>刷新证据状态</Button>
          {!fixed.archived && (
            <Button onClick={startEditing}>修改标题/备注</Button>
          )}
          <Link
            className="leader-briefing-cta"
            to={`/leader/briefings/${id}/present`}
          >
            打开会议视图 <ExpandOutlined />
          </Link>
        </Space>
      </div>
      {new URLSearchParams(window.location.search).get("previous") && (
        <Alert
          type="info"
          title={
            <>
              这是一份新修订；
              <Link
                to={`/leader/briefings/${new URLSearchParams(window.location.search).get("previous")}`}
              >
                查看上一版
              </Link>{" "}
              的事实和备注仍独立保存。
            </>
          }
        />
      )}
      <ReportFacts report={fixed} />
      {session?.role === "admin" && !fixed.archived && (
        <div className="leader-briefing-archive">
          <Button
            danger
            loading={busy}
            onClick={() =>
              Modal.confirm({
                title: "归档这份汇报？",
                content: "归档后历史版本仍可通过原链接读取。",
                okText: "归档",
                okButtonProps: { danger: true },
                cancelText: "取消",
                onOk: archive,
              })
            }
          >
            归档汇报
          </Button>
          {archiveError !== null && (
            <ErrorState error={archiveError} retry={() => void archive()} />
          )}
        </div>
      )}
      <Modal
        title="修改人工内容"
        open={editing}
        onCancel={() => {
          if (!busy && !locked) setEditing(false);
        }}
        onOk={() => void save()}
        okText="保存为新版本"
        okButtonProps={{ disabled: !title.trim(), loading: busy }}
      >
        <Alert
          type="info"
          title="系统事实、来源和警告保持原样；只会产生新的标题/备注版本。"
        />
        <label className="leader-checks-field">
          标题
          <Input
            aria-label="修订标题"
            disabled={locked}
            maxLength={200}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className="leader-checks-field">
          人工备注
          <Input.TextArea
            aria-label="修订人工备注"
            disabled={locked}
            maxLength={4000}
            rows={4}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </label>
        {locked && (
          <Alert
            type="warning"
            title="提交结果暂不确定；内容已锁定。请原样重试。"
          />
        )}
        {editError !== null && (
          <ErrorState error={editError} retry={() => void save()} />
        )}
      </Modal>
    </section>
  );
}

export function LeaderBriefingsPage() {
  const { briefingId } = useParams();
  if (briefingId === "new") return <BriefingCreate />;
  if (briefingId) return <BriefingDetail key={briefingId} id={briefingId} />;
  return <BriefingList />;
}

export function LeaderPresentationPage() {
  const { briefingId } = useParams();
  const report = useBriefing(briefingId ?? "");
  const [full, setFull] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  useEffect(() => {
    const sync = () => setFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);
  useEffect(() => {
    if (!report.data) return;
    const before = document.title;
    document.title = `${report.data.title} · 固定汇报`;
    return () => {
      document.title = before;
    };
  }, [report.data]);
  if (report.isPending) return <LoadingState />;
  if (report.isError)
    return (
      <ErrorState error={report.error} retry={() => void report.refetch()} />
    );
  if (!report.data) return null;
  const fixed = report.data;
  async function toggleFull() {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  }
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setCopyError(false);
    } catch {
      setCopyError(true);
    }
  }
  return (
    <main className="leader-presentation">
      <div className="leader-presentation-controls">
        <Link to={`/leader/briefings/${fixed.id}`}>
          <ArrowLeftOutlined /> 返回详情
        </Link>
        <Space wrap>
          <ThemeControl />
          <Button icon={<LinkOutlined />} onClick={() => void copyLink()}>
            {copied ? "已复制团队内链接" : "复制团队内链接"}
          </Button>
          {copyError && (
            <span role="alert">复制失败，请从浏览器地址栏复制链接。</span>
          )}
          <Button icon={<ExpandOutlined />} onClick={() => void toggleFull()}>
            {full ? "退出全屏" : "进入全屏"}
          </Button>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>
            打印 / 另存 PDF
          </Button>
        </Space>
      </div>
      <header className="leader-presentation-hero">
        <span className="leader-kicker">BATFISH / NETWORK BRIEFING</span>
        <p>固定事实 · 团队内共享 · 第 {fixed.version} 版</p>
        <h1>{fixed.title}</h1>
        <div className="leader-presentation-hero-meta">
          <span>{fixed.network_name}</span>
          <span>{fixed.snapshot_name}</span>
          <span>{when(fixed.created_at)}</span>
        </div>
      </header>
      <div className="leader-presentation-body">
        <ReportFacts report={fixed} meeting />
      </div>
      <footer className="leader-presentation-footer">
        <span>固定修订 {fixed.id}</span>
        <span>基于配置模型的检查结果；请结合范围、警告与来源解读。</span>
      </footer>
    </main>
  );
}
