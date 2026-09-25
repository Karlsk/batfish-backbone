import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  Pagination,
  Radio,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { useSession } from "../../app/session";
import { resourceKey } from "../../app/context";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { TraceSteps, actionLabel } from "../../components/TraceSteps";
import { cellText } from "../results/cells";
type Result = components["schemas"]["ResultEnvelope"];
type Flow = components["schemas"]["TraceFlow"];
function Dispositions({ values }: { values: Record<string, number> }) {
  return (
    <Space wrap>
      {Object.entries(values).map(([name, count]) => (
        <Tag key={name}>
          {actionLabel(name)} × {count}
        </Tag>
      ))}
    </Space>
  );
}
export function TraceResults({ result }: { result: Result }) {
  const session = useSession();
  const [offset, setOffset] = useState(0),
    [selected, setSelected] = useState<string>(),
    [headers, setHeaders] = useState<Flow | null>(null);
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "flows",
      { offset, limit: 5 },
      result.id,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/flows", {
          signal,
          params: {
            path: { result_id: result.id },
            query: { offset, limit: 5 },
          },
        }),
      ),
  });
  const flows = query.data?.items ?? [];
  const flow = flows.find((f) => f.flow_id === selected) ?? flows[0];
  return (
    <>
      <Alert
        showIcon
        type="info"
        title="单向配置模型推演；不是在线探测，也不证明回程连通。"
        description="Flow 是本次模型选出的具体报文头组合；多个路径可能有不同结论。路径统计仅覆盖已保存的 Flow 和已返回的路径。"
      />
      <Card className="diagnostic-card" title="报文流（Flow）">
        {query.isError ? (
          <ErrorState error={query.error} retry={() => void query.refetch()} />
        ) : (
          <Table<Flow>
            rowKey="flow_id"
            loading={query.isPending}
            dataSource={flows}
            rowSelection={{
              type: "radio",
              selectedRowKeys: flow ? [flow.flow_id] : [],
              onChange: (keys) => setSelected(String(keys[0])),
            }}
            onRow={(f) => ({ onClick: () => setSelected(f.flow_id) })}
            locale={{ emptyText: "没有返回 Flow；请核对起点、目标和参数。" }}
            pagination={{
              current: offset / 5 + 1,
              pageSize: 5,
              total: query.data?.total,
              showSizeChanger: false,
              onChange: (p) => {
                setSelected(undefined);
                setOffset((p - 1) * 5);
              },
            }}
            columns={[
              {
                title: "Flow",
                render: (_, f) => (
                  <Button type="link" onClick={() => setSelected(f.flow_id)}>
                    Flow {f.flow_id}
                  </Button>
                ),
              },
              {
                title: "实际报文",
                render: (_, f) => (
                  <div>
                    <div>
                      {cellText(f.headers.srcIp)} → {cellText(f.headers.dstIp)}
                    </div>
                    <small>
                      {cellText(f.headers.ipProtocol)} · 起点{" "}
                      {f.start_location ?? "未记录"}
                    </small>
                  </div>
                ),
              },
              {
                title: "路径",
                render: (_, f) => (
                  <span>
                    已返回 {f.returned_trace_count} / 报告 {f.trace_count}
                  </span>
                ),
              },
              {
                title: "已返回路径结论",
                render: (_, f) => (
                  <Dispositions values={f.dispositions ?? {}} />
                ),
              },
              {
                title: "详情",
                render: (_, f) => (
                  <Button
                    type="link"
                    onClick={(e) => {
                      e.stopPropagation();
                      setHeaders(f);
                    }}
                  >
                    报文头详情
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>
      {flow && (
        <FlowPaths
          key={`${result.id}:${flow.flow_id}`}
          result={result}
          flow={flow}
        />
      )}
      <DetailsDrawer
        open={!!headers}
        title="实际 Flow 报文头"
        onClose={() => setHeaders(null)}
        queryKey={resourceKey(
          session?.user_id ?? null,
          context,
          "flow-headers",
          { flowId: headers?.flow_id },
          result.id,
        )}
        load={async () => headers}
      />
    </>
  );
}
function FlowPaths({ result, flow }: { result: Result; flow: Flow }) {
  const session = useSession();
  const [offset, setOffset] = useState(0),
    [selected, setSelected] = useState(0),
    [raw, setRaw] = useState(false);
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const key = resourceKey(
    session?.user_id ?? null,
    context,
    "traces",
    { flowId: flow.flow_id, offset, limit: 5 },
    result.id,
  );
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/flows/{flow_id}/traces", {
          signal,
          params: {
            path: { result_id: result.id, flow_id: flow.flow_id },
            query: { offset, limit: 5 },
          },
        }),
      ),
  });
  const paths = query.data?.items ?? [],
    trace = paths[selected];
  return (
    <Card title={`Flow ${flow.flow_id} · 路径证据`}>
      {(flow.truncated || query.data?.truncated) && (
        <Alert
          showIcon
          type="warning"
          title={`路径未全部保存：已返回 ${flow.returned_trace_count} 条，引擎报告 ${flow.trace_count} 条。未显示路径的结论未知。`}
        />
      )}{" "}
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !paths.length ? (
        <EmptyState title="此 Flow 没有已保存路径" />
      ) : (
        <>
          <Radio.Group
            aria-label="选择路径"
            value={selected}
            onChange={(e) => {
              setRaw(false);
              setSelected(e.target.value);
            }}
            options={paths.map((p, index) => ({
              value: index,
              label: `路径 ${offset + index + 1} · ${actionLabel(p.disposition)}`,
            }))}
          />
          {trace && (
            <>
              <div className="path-heading">
                <Typography.Title level={4}>
                  {actionLabel(trace.disposition)}
                </Typography.Title>
                <Button onClick={() => setRaw(true)}>路径原始详情</Button>
              </div>
              <TraceSteps
                key={`${result.id}:${flow.flow_id}:${offset + selected}`}
                trace={trace}
                identity={`${result.id}:${flow.flow_id}:${offset + selected}`}
                queryKey={[...key, selected]}
              />
              <DetailsDrawer
                open={raw}
                title="路径原始详情"
                onClose={() => setRaw(false)}
                queryKey={[...key, selected, "raw"]}
                load={async () => trace}
              />
            </>
          )}
          <Pagination
            current={offset / 5 + 1}
            pageSize={5}
            total={query.data?.total}
            showSizeChanger={false}
            onChange={(p) => {
              setSelected(0);
              setRaw(false);
              setOffset((p - 1) * 5);
            }}
          />
        </>
      )}
    </Card>
  );
}
