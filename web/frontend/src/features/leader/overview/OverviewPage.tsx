import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Tag, Typography } from "antd";
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import { Link, useParams } from "react-router-dom";
import { api, unwrap } from "../../../api/client";
import type { components } from "../../../api/schema";
import { chooseEntry } from "../../../app/entry";
import { resourceKey, useResourceContext } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ErrorState } from "../../../components/States";
import { describeNetwork } from "./model";

type CardData = components["schemas"]["NetworkOverview"];
const time = (value: string) =>
  new Date(value).toLocaleString("zh-CN", { hour12: false });
const shortId = (value: string) => value.slice(0, 8);

function StatePill({ value }: { value: CardData }) {
  const view = describeNetwork(value);
  return (
    <div className="leader-overview-state">
      <Tag
        color={
          view.tone === "good"
            ? "green"
            : view.tone === "warning"
              ? "gold"
              : "default"
        }
      >
        {view.readiness}
      </Tag>
      <span>{view.check}</span>
    </div>
  );
}

function Warnings({ card }: { card: CardData }) {
  const warnings = describeNetwork(card).warnings;
  return warnings.length ? (
    <ul className="leader-overview-warnings">
      {warnings.map((warning) => (
        <li key={warning}>{warning}</li>
      ))}
    </ul>
  ) : null;
}

function SummaryCard({ card }: { card: CardData }) {
  const ready = card.latest_ready_snapshot;
  const result = card.latest_result;
  return (
    <article
      className="leader-overview-card"
      aria-label={`网络 ${card.display_name} ${shortId(card.network_id)}`}
    >
      <div className="leader-overview-card-top">
        <span className="leader-overview-id">
          网络 / {shortId(card.network_id)}
        </span>
        <StatePill value={card} />
      </div>
      <Typography.Title level={3}>{card.display_name}</Typography.Title>
      <p className="leader-overview-card-source">
        {ready
          ? `就绪快照：${ready.display_name} · ${time(ready.created_at)}`
          : "尚无就绪快照，请先上传配置并完成初始化。"}
      </p>
      <Warnings card={card} />
      <div className="leader-overview-card-bottom">
        <span>{card.concern_count} 个业务关注项</span>
        <span>
          {result
            ? `结果 ${shortId(result.id)} · ${time(result.created_at)}`
            : "暂无可读结果"}
        </span>
      </div>
      <Link
        className="leader-card-link"
        to={`/leader/networks/${card.network_id}`}
      >
        查看网络详情 <ArrowRightOutlined />
      </Link>
    </article>
  );
}

export function LeaderOverviewPage() {
  const session = useSession();
  const { network, snapshot } = useResourceContext();
  const query = useInfiniteQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: null, snapshotId: null },
      "leader-overview",
    ),
    queryFn: ({ pageParam, signal }) =>
      unwrap(
        api.GET("/api/v1/leader/overview", {
          signal,
          params: { query: { offset: pageParam, limit: 20 } },
        }),
      ),
    initialPageParam: 0,
    getNextPageParam: (page) =>
      page.offset + page.items.length < page.total
        ? page.offset + page.items.length
        : undefined,
    enabled: !!session,
  });
  const first = query.data?.pages[0];
  const cards = query.data?.pages.flatMap((page) => page.items) ?? [];
  const counts = first?.counts;
  const readyRecords =
    (counts?.snapshot_states.ready ?? 0) +
    (counts?.snapshot_states.ready_with_warnings ?? 0);
  const activeJobs =
    (counts?.analysis_job_states.queued ?? 0) +
    (counts?.analysis_job_states.running ?? 0);
  return (
    <section className="leader-overview-page">
      <div className="leader-hero">
        <div className="leader-hero-orbit" aria-hidden="true" />
        <div className="leader-hero-content">
          <span className="leader-kicker">NETWORK INSIGHT / 日常总览</span>
          <Typography.Title level={1}>网络总览</Typography.Title>
          <p>
            所有共享网络的配置快照、检查任务与结果来源，一眼看清；具体结论以已保存的检查证据为准。
          </p>
          {network && (
            <p className="leader-context-note">
              技术工作台当前选择：{network.name}
              {snapshot ? ` / ${snapshot.name}` : ""}
            </p>
          )}
        </div>
        <div className="leader-hero-index" aria-hidden="true">
          01 / OVERVIEW
        </div>
      </div>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : query.isPending ? (
        <Card loading className="leader-overview-loading" />
      ) : (
        <>
          <div className="leader-overview-metrics" aria-label="全量事实汇总">
            <div>
              <span>共享网络</span>
              <strong>{first?.total ?? 0}</strong>
              <small>未删除网络总数</small>
            </div>
            <div>
              <span>就绪快照记录</span>
              <strong>{readyRecords}</strong>
              <small>含历史快照；不是网络健康数</small>
            </div>
            <div>
              <span>运行中的分析</span>
              <strong>{activeJobs}</strong>
              <small>排队与运行中任务</small>
            </div>
          </div>
          <section
            className="leader-overview-recent"
            aria-labelledby="leader-recent-title"
          >
            <div className="leader-overview-section-head">
              <div>
                <span className="leader-kicker">RECENT CHANGES</span>
                <Typography.Title level={2} id="leader-recent-title">
                  最近变更比较
                </Typography.Title>
                <p>按保存时间列出最近五次比较；基线与候选方向保持不变。</p>
              </div>
            </div>
            {first?.recent_comparisons.length ? (
              <div className="leader-overview-recent-grid">
                {first.recent_comparisons.map((item) => (
                  <article className="leader-recent-card" key={item.id}>
                    <span className="leader-kicker">
                      {time(item.created_at)} ·{" "}
                      {item.coverage === "limited"
                        ? "覆盖有限"
                        : "覆盖记录完整"}
                    </span>
                    <strong>{item.display_name}</strong>
                    <p>
                      {item.network_display_name} · 网络{" "}
                      {shortId(item.network_id)}
                    </p>
                    <small>
                      基线 {shortId(item.baseline_snapshot_id)} → 候选{" "}
                      {shortId(item.candidate_snapshot_id)} · 比较{" "}
                      {shortId(item.id)}
                    </small>
                    <Link to={`/leader/networks/${item.network_id}`}>
                      查看所属网络 <ArrowRightOutlined />
                    </Link>
                  </article>
                ))}
              </div>
            ) : (
              <p className="leader-overview-recent-empty">
                尚无已保存的变更比较；需要明确基线和候选快照后才能检查。
              </p>
            )}
          </section>
          {first?.total === 0 ? (
            <Card className="leader-overview-empty">
              <Empty description="尚无共享网络">
                <Link to="/networks" onClick={() => chooseEntry("technical")}>
                  <Button type="primary">创建第一个网络</Button>
                </Link>
              </Empty>
            </Card>
          ) : (
            <>
              <div className="leader-overview-section-head">
                <div>
                  <span className="leader-kicker">ALL NETWORKS</span>
                  <Typography.Title level={2}>网络一览</Typography.Title>
                  <p>
                    已展示 {cards.length} / {first?.total}{" "}
                    个网络。卡片仅描述配置与检查状态。
                  </p>
                </div>
                <Link to="/leader/concerns">
                  管理业务关注项 <ArrowRightOutlined />
                </Link>
              </div>
              <div className="leader-overview-grid">
                {cards.map((card) => (
                  <SummaryCard key={card.network_id} card={card} />
                ))}
              </div>
              {query.hasNextPage && (
                <div className="leader-overview-more">
                  <Button
                    loading={query.isFetchingNextPage}
                    onClick={() => void query.fetchNextPage()}
                  >
                    加载更多网络
                  </Button>
                </div>
              )}
            </>
          )}
          <div className="leader-overview-next">
            <DatabaseOutlined />
            <div>
              <strong>变更与故障检查</strong>
              <p>
                比较与故障模拟需要明确的基线、候选和检查范围。进入网络详情可查看该网络已有比较，或前往技术工作台操作。
              </p>
            </div>
            <Link to="/changes" onClick={() => chooseEntry("technical")}>
              前往技术工作台 <ArrowRightOutlined />
            </Link>
          </div>
        </>
      )}
      <p className="leader-footnote">
        汇总来自已上传配置与保存结果，不代表在线监控或真实设备转发状态。
      </p>
    </section>
  );
}

export function LeaderNetworkPage() {
  const { networkId } = useParams();
  const session = useSession();
  const { selectNetwork } = useResourceContext();
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: networkId ?? null, snapshotId: null },
      "leader-network-detail",
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/leader/networks/{network_id}", {
          signal,
          params: { path: { network_id: networkId! } },
        }),
      ),
    enabled: !!session && !!networkId,
  });
  const concerns = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: networkId ?? null, snapshotId: null },
      "leader-network-concerns",
      { limit: 10 },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/business-concerns", {
          signal,
          params: { query: { network_id: networkId!, offset: 0, limit: 10 } },
        }),
      ),
    enabled: !!session && !!networkId,
  });
  const comparisons = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: networkId ?? null, snapshotId: null },
      "leader-network-comparisons",
      { limit: 3 },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/comparisons", {
          signal,
          params: {
            path: { network_id: networkId! },
            query: { offset: 0, limit: 3 },
          },
        }),
      ),
    enabled: !!session && !!networkId,
  });
  if (query.isError)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  if (!query.data) return <Card loading />;
  const card = query.data;
  const view = describeNetwork(card);
  const ready = card.latest_ready_snapshot;
  const newest = card.latest_snapshot;
  const job = card.latest_job;
  const result = card.latest_result;
  return (
    <section className="leader-network-page">
      <Link className="leader-back-link" to="/leader/overview">
        <ArrowLeftOutlined /> 返回全部网络
      </Link>
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">NETWORK DETAIL / 网络详情</span>
          <Typography.Title level={1}>{card.display_name}</Typography.Title>
          <p>网络编号 {card.network_id} · 配置、任务和结果各保留固定来源。</p>
        </div>
        <StatePill value={card} />
      </div>
      <Warnings card={card} />
      <div className="leader-network-summary-grid">
        <Card title="当前快照" className="leader-network-panel">
          {newest ? (
            <>
              <strong>{newest.display_name}</strong>
              <p>
                状态：{newest.status} · {time(newest.created_at)}
              </p>
              <small>快照 {newest.id}</small>
            </>
          ) : (
            <p>尚未上传配置快照。</p>
          )}
          {ready && (
            <div className="leader-network-evidence">
              <span>最近就绪来源</span>
              <strong>{ready.display_name}</strong>
              <p>
                {time(ready.created_at)} · 节点 {ready.node_count ?? "未知"} ·
                解析问题 {ready.issue_count ?? "未知"}
              </p>
              <small>快照 {ready.id}</small>
              <Link
                to={`/networks/${card.network_id}/snapshots/${ready.id}/diagnostics`}
                onClick={() => chooseEntry("technical")}
              >
                查看解析证据 <ArrowRightOutlined />
              </Link>
            </div>
          )}
          {!ready && (
            <Link to="/networks" onClick={() => chooseEntry("technical")}>
              上传并初始化配置 <ArrowRightOutlined />
            </Link>
          )}
        </Card>
        <Card title="最近检查" className="leader-network-panel">
          <strong>{view.check}</strong>
          {job ? (
            <>
              <p>
                {job.phase} · {time(job.created_at)}
              </p>
              <small>
                任务 {job.id} · 来源快照 {job.snapshot_id}
              </small>
              <Link
                to={`/jobs/${job.id}`}
                onClick={() => chooseEntry("technical")}
              >
                查看任务与进度 <ArrowRightOutlined />
              </Link>
            </>
          ) : (
            <p>这份就绪快照尚无检查任务。</p>
          )}
          {ready && !job && (
            <Link
              to="/analysis"
              onClick={() => {
                chooseEntry("technical");
                void selectNetwork({
                  id: card.network_id,
                  name: card.display_name,
                });
              }}
            >
              在技术工作台发起检查 <ArrowRightOutlined />
            </Link>
          )}
        </Card>
        <Card title="已保存结果" className="leader-network-panel">
          {result ? (
            <>
              <strong>
                {result.coverage === "limited"
                  ? "覆盖有限"
                  : result.coverage === "complete"
                    ? "覆盖记录完整"
                    : "覆盖范围未知"}
              </strong>
              <p>
                {time(result.created_at)} · {result.warning_count} 条警告
                {result.truncated ? " · 已截断" : ""}
              </p>
              <small>
                结果 {result.id} · 来源快照 {result.snapshot_id}
              </small>
              <Link
                to={`/results/${result.id}`}
                onClick={() => chooseEntry("technical")}
              >
                查看结果证据 <ArrowRightOutlined />
              </Link>
            </>
          ) : (
            <p>尚无与最近就绪快照对应的可读结果。</p>
          )}
        </Card>
      </div>
      <div className="leader-network-lower">
        <Card
          title={`业务关注项 · ${card.concern_count}`}
          className="leader-network-panel"
        >
          {concerns.isError ? (
            <ErrorState
              error={concerns.error}
              retry={() => void concerns.refetch()}
            />
          ) : concerns.isPending ? (
            <Card loading />
          ) : !concerns.data?.items.length ? (
            <p>尚未配置业务关注项；系统不会自动推断业务影响。</p>
          ) : (
            <ul className="leader-network-list">
              {concerns.data.items.map((item) => (
                <li key={item.id}>
                  <span>
                    {item.name} ·{" "}
                    {item.priority === "high"
                      ? "高"
                      : item.priority === "medium"
                        ? "中"
                        : "低"}
                    重要度
                  </span>
                  <small>
                    {item.flows.length} 条流量 · 映射 v{item.version}
                  </small>
                </li>
              ))}
            </ul>
          )}
          <Link
            to="/leader/concerns"
            onClick={() =>
              void selectNetwork({
                id: card.network_id,
                name: card.display_name,
              })
            }
          >
            查看全部关注项 <ArrowRightOutlined />
          </Link>
        </Card>
        <Card title="最近比较" className="leader-network-panel">
          {comparisons.isError ? (
            <ErrorState
              error={comparisons.error}
              retry={() => void comparisons.refetch()}
            />
          ) : comparisons.isPending ? (
            <Card loading />
          ) : !comparisons.data?.items.length ? (
            <p>该网络尚无双快照比较。</p>
          ) : (
            <ul className="leader-network-list">
              {comparisons.data.items.map((item) => (
                <li key={item.id}>
                  <span>{item.display_name}</span>
                  <small>
                    {time(item.created_at)} · 基线{" "}
                    {shortId(item.baseline_snapshot_id)} → 候选{" "}
                    {shortId(item.candidate_snapshot_id)}
                  </small>
                  <small>比较 {item.id}</small>
                </li>
              ))}
            </ul>
          )}
          <Link
            to="/changes"
            onClick={() => {
              chooseEntry("technical");
              void selectNetwork({
                id: card.network_id,
                name: card.display_name,
              });
            }}
          >
            进入变更工作台 <ArrowRightOutlined />
          </Link>
        </Card>
      </div>
      {card.readiness === "warning" && (
        <Alert
          className="leader-network-limit"
          type="warning"
          showIcon
          title="请先查看快照质量与模型限制，再解读检查结果。"
        />
      )}
      <p className="leader-footnote">
        网络详情只汇总已保存的事实。最近结果可能早于最近失败或中断的任务，时间与来源分别标注。
      </p>
    </section>
  );
}
