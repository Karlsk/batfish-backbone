import { useState } from "react";
import { Alert, Button, Card, Empty, Select } from "antd";
import { useQuery } from "@tanstack/react-query";
import type { components } from "../../../api/schema";
import { api, unwrap } from "../../../api/client";
import { resourceKey } from "../../../app/context";
import { useSession } from "../../../app/session";
import { ErrorState, LoadingState } from "../../../components/States";
import { GraphCanvas } from "../../topology/GraphCanvas";
import { prepareGraph, views, type GraphSelection } from "../../topology/model";
import { graphSourceLabel } from "../checks/advanced";

type Result = components["schemas"]["ResultEnvelope"];

export function FocusedGraph({ result }: { result: Result }) {
  const session = useSession();
  const [focus, setFocus] = useState<string | null>(null);
  const [hops, setHops] = useState(1);
  const [selection, setSelection] = useState<GraphSelection | null>(null);
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const root = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "leader-graph-root",
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
  const graph = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "leader-graph-focus",
      { focus, hops },
      result.id,
    ),
    enabled: !!focus,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/graph", {
          signal,
          params: {
            path: { result_id: result.id },
            query: { focus_node: focus!, hops, limit: 200 },
          },
        }),
      ),
  });
  const query = focus ? graph : root;
  const data = query.data;
  const bounded = data ? prepareGraph(data) : null;
  const selected =
    selection?.kind === "node"
      ? data?.nodes.find((item) => item.id === selection.id)
      : data?.edges.find((item) => item.id === selection?.id);
  return (
    <Card title="04 / 模型关系图" className="leader-checks-panel">
      <p className="leader-checks-note">
        图中边来自已保存的配置模型；三层边为推导关系，协议边也不代表实时会话或物理链路。
      </p>
      {root.isError ? (
        <ErrorState error={root.error} retry={() => void root.refetch()} />
      ) : root.isPending ? (
        <LoadingState />
      ) : (
        <>
          <div className="leader-graph-controls">
            <Select
              aria-label="聚焦设备"
              value={focus}
              allowClear
              showSearch={{ optionFilterProp: "label" }}
              virtual={false}
              placeholder="全部已保存设备"
              options={root.data.nodes.map((item) => ({
                value: item.id,
                label: item.label,
              }))}
              onChange={(value) => {
                setFocus(value ?? null);
                setSelection(null);
              }}
            />
            <Select
              aria-label="邻居跳数"
              value={hops}
              disabled={!focus}
              virtual={false}
              options={[0, 1, 2, 3].map((value) => ({
                value,
                label: `${value} 跳`,
              }))}
              onChange={(value) => {
                setHops(value);
                setSelection(null);
              }}
            />
          </div>
          {root.data.nodes.length >= 200 && (
            <Alert
              type="warning"
              title="设备候选只列前 200 台，其他设备可在技术工作台聚焦。"
            />
          )}
          {query.isError ? (
            <ErrorState
              error={query.error}
              retry={() => void query.refetch()}
            />
          ) : query.isPending ? (
            <LoadingState />
          ) : data && bounded ? (
            <>
              <p aria-live="polite">
                {views[data.edge_type]} · {graphSourceLabel(data.source)} ·{" "}
                {focus ? `${focus} 的 ${hops} 跳邻域` : "已保存范围"} ·{" "}
                {bounded.nodes.length} 台设备 / {bounded.edges.length}{" "}
                条有向关系
              </p>
              {(bounded.truncated || result.truncated) && (
                <Alert
                  type="warning"
                  title="图形范围已截断；可见设备和边不能代表完整网络。"
                />
              )}
              {bounded.nodes.length ? (
                <GraphCanvas graph={data} onSelect={setSelection} />
              ) : (
                <Empty description="此范围没有设备" />
              )}
              {!bounded.edges.length && !!bounded.nodes.length && (
                <Alert
                  type="info"
                  title="此范围未返回关系；不能据此判断物理链路断开。"
                />
              )}
              <div className="leader-graph-nodes" aria-label="设备列表">
                {bounded.nodes.map((node) => (
                  <Button
                    key={node.id}
                    onClick={() => setSelection({ kind: "node", id: node.id })}
                  >
                    {node.label}
                  </Button>
                ))}
              </div>
              {selected && (
                <div className="leader-checks-source" aria-live="polite">
                  <strong>
                    {selection?.kind === "node" ? "设备" : "关系"}：
                    {selection?.id}
                  </strong>
                  <span>
                    {selection?.kind === "edge" && "source" in selected
                      ? `${selected.source} → ${selected.target}`
                      : "来自本次保存的模型图"}
                  </span>
                </div>
              )}
            </>
          ) : null}
        </>
      )}
    </Card>
  );
}
