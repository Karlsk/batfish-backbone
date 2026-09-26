import { useEffect, useRef, useState } from "react";
import {
  Alert,
  AutoComplete,
  Button,
  Card,
  Collapse,
  Select,
  Space,
  Table,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, unwrap } from "../../api/client";
import { resourceKey, useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import { ErrorState, EmptyState, LoadingState } from "../../components/States";
import { GraphCanvas } from "./GraphCanvas";
import { TopologyForm } from "./TopologyForm";
import { prepareGraph, views, type GraphSelection } from "./model";
export function GraphResult({
  result,
}: {
  result: components["schemas"]["ResultEnvelope"];
}) {
  const session = useSession(),
    navigate = useNavigate(),
    selection = useResourceContext();
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const [focus, setFocus] = useState<string>(),
    [input, setInput] = useState(""),
    [hops, setHops] = useState(1),
    [detail, setDetail] = useState<GraphSelection | null>(null),
    [navigationError, setNavigationError] = useState<unknown>(),
    [navigating, setNavigating] = useState(false);
  const routeGeneration = useRef(0);
  const routeInFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      routeGeneration.current += 1;
      routeInFlight.current = false;
    };
  }, [result.id]);
  const root = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "graph-index",
      {},
      result.id,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/graph", {
          signal,
          params: { path: { result_id: result.id }, query: { limit: 200 } },
        }),
      ),
  });
  const activeFocus = focus ?? root.data?.nodes[0]?.id;
  const params = { focus_node: activeFocus, hops, limit: 200 };
  const focused = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "graph",
      params,
      result.id,
    ),
    enabled: !!activeFocus,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/graph", {
          signal,
          params: { path: { result_id: result.id }, query: params },
        }),
      ),
  });
  const query = activeFocus ? focused : root;
  const data = query.data;
  async function routes(node: string) {
    if (routeInFlight.current) return;
    routeInFlight.current = true;
    const generation = ++routeGeneration.current;
    const current = () =>
      mounted.current && generation === routeGeneration.current;
    setNavigating(true);
    setNavigationError(undefined);
    try {
      const [network, snapshot] = await Promise.all([
        unwrap(
          api.GET("/api/v1/networks/{network_id}", {
            params: { path: { network_id: context.networkId } },
          }),
        ),
        unwrap(
          api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
            params: {
              path: {
                network_id: context.networkId,
                snapshot_id: context.snapshotId!,
              },
            },
          }),
        ),
      ]);
      if (!current()) return;
      if (
        !(await selection.selectNetwork({
          id: network.id,
          name: network.display_name,
        }))
      )
        return;
      if (!current()) return;
      if (
        !(await selection.selectSnapshot({
          id: snapshot.id,
          name: snapshot.display_name,
          networkId: network.id,
        }))
      )
        return;
      if (!current()) return;
      navigate("/analysis/routes", {
        state: { presetNode: { ...context, node } },
      });
    } catch (error) {
      if (current()) setNavigationError(error);
    } finally {
      if (current()) {
        routeInFlight.current = false;
        setNavigating(false);
      }
    }
  }
  if (root.isError)
    return <ErrorState error={root.error} retry={() => void root.refetch()} />;
  if (root.isPending) return <LoadingState />;
  const graph = data ? prepareGraph(data) : null;
  const item =
    detail?.kind === "node"
      ? data?.nodes.find((n) => n.id === detail.id)
      : data?.edges.find((e) => e.id === detail?.id);
  return (
    <Card title="拓扑关系证据">
      <Alert
        type="info"
        title="三层为配置推导关系；BGP / OSPF / ISIS 为协议关系，均不是实时链路通断或会话健康。"
      />
      <Collapse
        className="action-bar"
        items={[
          {
            key: "view",
            label: "切换关系视图或计算筛选条件",
            children: (
              <TopologyForm
                key={result.id}
                networkId={context.networkId}
                snapshotId={context.snapshotId!}
                initialView={data?.edge_type ?? "layer3"}
              />
            ),
          },
        ]}
      />
      <Space wrap className="filter-bar">
        <AutoComplete
          aria-label="聚焦设备"
          value={input}
          onChange={setInput}
          options={root.data.nodes.map((n) => ({
            value: n.id,
            label: n.label,
          }))}
          placeholder={activeFocus ?? "输入完整设备名"}
          style={{ width: 240 }}
          filterOption={(text, option) =>
            String(option?.value ?? "")
              .toLowerCase()
              .includes(text.toLowerCase())
          }
        />
        <Button
          onClick={() => {
            if (input) {
              setDetail(null);
              setFocus(input);
            }
          }}
        >
          查看邻域
        </Button>
        <Select
          aria-label="邻居跳数"
          value={hops}
          virtual={false}
          onChange={(value) => {
            setDetail(null);
            setHops(value);
          }}
          options={[0, 1, 2, 3, 4, 5].map((value) => ({
            value,
            label: value === 0 ? "仅设备" : `${value} 跳邻居`,
          }))}
        />
      </Space>
      {root.data.nodes.length >= 200 && (
        <Alert
          type="warning"
          title="候选列表最多200台设备；可输入完整设备名读取其他设备邻域。"
        />
      )}
      {navigationError != null && <ErrorState error={navigationError} />}
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : query.isPending ? (
        <LoadingState />
      ) : graph && data ? (
        <>
          <p aria-live="polite">
            {views[data.edge_type]} ·{" "}
            {activeFocus ? `${activeFocus} 的 ${hops} 跳邻域` : "已保存范围"} ·
            显示 {graph.nodes.length} 台设备、{graph.edges.length} 条有向关系
          </p>
          {graph.truncated && (
            <Alert
              type="warning"
              title="范围受限：当前图或已保存结果存在截断，最多展示200台设备/200条关系，不能视为完整网络。"
            />
          )}
          {!graph.nodes.length ? (
            <EmptyState title="当前计算范围没有设备；请核对选择条件。" />
          ) : (
            <GraphCanvas graph={data} onSelect={setDetail} />
          )}
          {!graph.edges.length && graph.nodes.length > 0 && (
            <Alert
              type="info"
              title="此范围没有该类型关系，已保留孤立设备；缺少边不能证明物理断线。"
            />
          )}
          <Typography.Title level={4}>设备列表（键盘可用）</Typography.Title>
          <Table
            size="small"
            rowKey="id"
            pagination={{ pageSize: 10, showSizeChanger: false }}
            dataSource={graph.nodes}
            columns={[
              {
                title: "设备",
                dataIndex: "label",
                render: (value: string) => (
                  <span className="result-cell" title={value}>
                    {value}
                  </span>
                ),
              },
              {
                title: "操作",
                render: (_, node) => (
                  <Space wrap>
                    <Button
                      aria-label={`设备详情 ${node.id}`}
                      onClick={() => setDetail({ kind: "node", id: node.id })}
                    >
                      详情
                    </Button>
                    <Button
                      aria-label={`聚焦 ${node.id}`}
                      onClick={() => {
                        setFocus(node.id);
                        setHops(1);
                        setInput(node.id);
                        setDetail(null);
                      }}
                    >
                      一跳邻域
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
          <Typography.Title level={4}>关系列表（方向与接口）</Typography.Title>
          <Table
            size="small"
            rowKey="id"
            pagination={{ pageSize: 10, showSizeChanger: false }}
            scroll={{ x: 640 }}
            dataSource={graph.edges}
            columns={[
              {
                title: "起点",
                render: (_, edge) => (
                  <span>
                    {edge.source} · {edge.source_interface ?? "接口未提供"}
                  </span>
                ),
              },
              {
                title: "终点",
                render: (_, edge) => (
                  <span>
                    {edge.target} · {edge.target_interface ?? "接口未提供"}
                  </span>
                ),
              },
              {
                title: "证据",
                render: (_, edge) => (
                  <Button
                    aria-label={`关系详情 ${edge.source} ${edge.source_interface ?? ""} 到 ${edge.target} ${edge.target_interface ?? ""}`}
                    onClick={() => setDetail({ kind: "edge", id: edge.id })}
                  >
                    接口详情
                  </Button>
                ),
              },
            ]}
          />
          <DetailsDrawer
            open={!!item}
            title={
              detail?.kind === "node" ? "设备与接口证据" : "关系与接口证据"
            }
            onClose={() => {
              routeGeneration.current += 1;
              routeInFlight.current = false;
              setNavigating(false);
              setDetail(null);
            }}
            queryKey={resourceKey(
              session?.user_id ?? null,
              context,
              "graph-detail",
              { detail },
              result.id,
            )}
            load={async () => item}
            render={(item) => (
              <>
                {detail?.kind === "node" && (
                  <>
                    <Button
                      loading={navigating}
                      onClick={() => void routes(item!.id)}
                    >
                      查询该设备路由
                    </Button>
                    <p>
                      涉及接口：
                      {data.edges
                        .filter(
                          (e) => e.source === item!.id || e.target === item!.id,
                        )
                        .map((e) =>
                          e.source === item!.id
                            ? e.source_interface
                            : e.target_interface,
                        )
                        .filter(Boolean)
                        .filter((v, i, a) => a.indexOf(v) === i)
                        .join("、") || "当前关系未提供接口"}
                    </p>
                  </>
                )}
                <pre className="raw-detail">
                  {JSON.stringify(
                    {
                      source: data.source,
                      context: result.context,
                      evidence: item,
                    },
                    null,
                    2,
                  )}
                </pre>
              </>
            )}
          />
        </>
      ) : null}
    </Card>
  );
}
