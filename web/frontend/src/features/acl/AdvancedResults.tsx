import { useState, type ReactNode } from "react";
import { Alert, Button, Card, Collapse, Descriptions, Table } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, unwrap } from "../../api/client";
import { resourceKey, useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import { ErrorState } from "../../components/States";
import { cellText } from "../results/cells";
import { filterDraftFromWitness } from "./advanced-requests";

type Result = components["schemas"]["ResultEnvelope"];
type Row = Record<string, unknown>;

function record(value: unknown): Row {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Row)
    : {};
}
function nodeName(value: unknown) {
  if (typeof value === "string") return value;
  return typeof record(value).name === "string"
    ? String(record(value).name)
    : "未知设备";
}
function names(value: unknown) {
  const values = record(value).values;
  return Array.isArray(values) ? values.map(cellText).join("、") : "范围未知";
}

export function reachabilityReason(row: Row): {
  kind: "blocked" | "empty" | "unknown";
  label: string;
} {
  if (
    row.Reason === "BLOCKING_LINES" &&
    Array.isArray(row.Blocking_Lines) &&
    row.Blocking_Lines.length
  )
    return { kind: "blocked", label: "被前序规则阻挡" };
  if (row.Reason === "INDEPENDENTLY_UNMATCHABLE")
    return { kind: "empty", label: "匹配条件本身为空" };
  return { kind: "unknown", label: "原因待核对" };
}

function useRows(result: Result, offset: number, kind: string) {
  const session = useSession();
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  return useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      kind,
      { offset },
      result.id,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/rows", {
          signal,
          params: {
            path: { result_id: result.id },
            query: { offset, limit: 20 },
          },
        }),
      ),
  });
}

function Scope({ result, search }: { result: Result; search: boolean }) {
  const request = record(result.effective_parameters.request);
  const headers = record(record(request.options).headers);
  return (
    <>
      <p>
        查询范围：设备 {names(request.nodes)}；ACL {names(request.filters)}
        {search && (
          <>
            ；动作 {cellText(request.action)}；源 {cellText(headers.source_ip)}
            ；目标 {cellText(headers.destination_ip)}
          </>
        )}
      </p>
      <Alert
        type="info"
        title="结果固定来自配置模型和上述查询范围，不代表现场转发或全网安全。"
        description={
          <Link
            to={
              "/networks/" +
              result.context.network_id +
              "/snapshots/" +
              result.context.snapshot_id +
              "/diagnostics"
            }
          >
            查看快照解析与模型限制
          </Link>
        }
      />
    </>
  );
}

export function FilterSearchResult({ result }: { result: Result }) {
  const [offset, setOffset] = useState(0);
  const [detail, setDetail] = useState<Row | null>(null);
  const [navigationError, setNavigationError] = useState<unknown>();
  const [navigating, setNavigating] = useState(false);
  const selection = useResourceContext();
  const navigate = useNavigate();
  const query = useRows(result, offset, "acl-search-rows");
  const rows = query.data?.rows ?? [];
  const partial =
    result.truncated ||
    query.data?.truncated ||
    (query.data?.total ?? 0) > rows.length;
  function witness(row: Row) {
    const value = {
      networkId: result.context.network_id,
      snapshotId: result.context.snapshot_id,
      node: nodeName(row.Node),
      filter: row.Filter_Name,
      flow: row.Flow,
    };
    return filterDraftFromWitness(
      value,
      result.context.network_id,
      result.context.snapshot_id,
    )
      ? value
      : null;
  }
  async function testWitness(row: Row) {
    const value = witness(row);
    if (!value || navigating) return;
    setNavigating(true);
    setNavigationError(undefined);
    try {
      const [network, snapshot] = await Promise.all([
        unwrap(
          api.GET("/api/v1/networks/{network_id}", {
            params: { path: { network_id: result.context.network_id } },
          }),
        ),
        unwrap(
          api.GET("/api/v1/networks/{network_id}/snapshots/{snapshot_id}", {
            params: {
              path: {
                network_id: result.context.network_id,
                snapshot_id: result.context.snapshot_id,
              },
            },
          }),
        ),
      ]);
      if (
        !(await selection.selectNetwork({
          id: network.id,
          name: network.display_name,
        }))
      )
        return;
      if (
        !(await selection.selectSnapshot({
          id: snapshot.id,
          name: snapshot.display_name,
          networkId: network.id,
        }))
      )
        return;
      navigate("/acl", { state: { presetAcl: value } });
    } catch (error) {
      setNavigationError(error);
    } finally {
      setNavigating(false);
    }
  }
  return (
    <Card title="ACL 条件搜索">
      <Scope result={result} search />
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !query.isPending ? (
        <Alert
          className="action-bar"
          type="warning"
          title={
            rows.length
              ? "找到所选范围内的示例流量；逐条核对。"
              : "当前条件未找到示例流量；不能据此证明策略安全。"
          }
          description={
            partial
              ? "结果分页中或已截断；当前页不足以汇总整个范围。"
              : undefined
          }
        />
      ) : null}
      {navigationError != null && <ErrorState error={navigationError} />}
      <Table<Row & { _key: string }>
        rowKey="_key"
        loading={query.isPending}
        dataSource={rows.map((row, index) => ({
          ...row,
          _key: result.id + ":" + (offset + index),
        }))}
        locale={{ emptyText: "当前条件无示例流量；结论未知。" }}
        pagination={{
          current: offset / 20 + 1,
          pageSize: 20,
          total: query.data?.total,
          showSizeChanger: false,
          onChange: (page) => setOffset((page - 1) * 20),
        }}
        columns={[
          {
            title: "设备 / ACL",
            key: "scope",
            render: (_, row) =>
              nodeName(row.Node) + " / " + cellText(row.Filter_Name),
          },
          {
            title: "示例动作",
            key: "action",
            render: (_, row) => cellText(row.Action),
          },
          {
            title: "命中依据",
            key: "line",
            render: (_, row) => cellText(row.Line_Content),
          },
          {
            title: "操作",
            key: "operations",
            render: (_, row) => (
              <>
                <Button type="link" onClick={() => setDetail(row)}>
                  查看证据
                </Button>
                {witness(row) && (
                  <Button
                    type="link"
                    loading={navigating}
                    onClick={() => void testWitness(row)}
                  >
                    用此 Flow 测试 ACL
                  </Button>
                )}
              </>
            ),
          },
        ]}
      />
      <RawDetail
        result={result}
        row={detail}
        onClose={() => setDetail(null)}
        title="搜索示例详情"
        items={
          detail
            ? [
                {
                  key: "flow",
                  label: "实际 Flow",
                  children: (
                    <pre className="raw-detail">
                      {JSON.stringify(detail.Flow, null, 2)}
                    </pre>
                  ),
                },
                {
                  key: "line",
                  label: "命中依据",
                  children: cellText(detail.Line_Content),
                },
                {
                  key: "source",
                  label: "配置来源",
                  children:
                    Array.isArray(detail.Source_References) &&
                    detail.Source_References.length ? (
                      <pre className="raw-detail">
                        {JSON.stringify(detail.Source_References, null, 2)}
                      </pre>
                    ) : (
                      "没有可用来源引用"
                    ),
                },
              ]
            : []
        }
      />
    </Card>
  );
}

function RawDetail({
  result,
  row,
  onClose,
  title,
  items,
}: {
  result: Result;
  row: Row | null;
  onClose: () => void;
  title: string;
  items: { key: string; label: string; children: ReactNode }[];
}) {
  const session = useSession();
  return (
    <DetailsDrawer
      open={!!row}
      title={title}
      onClose={onClose}
      queryKey={resourceKey(
        session?.user_id ?? null,
        {
          networkId: result.context.network_id,
          snapshotId: result.context.snapshot_id,
        },
        "acl-advanced-detail",
        row,
        result.id,
      )}
      load={async () => row}
      render={(value) =>
        value && (
          <>
            <Descriptions column={1} bordered size="small" items={items} />
            <Collapse
              items={[
                {
                  key: "raw",
                  label: "原始 SDK 证据",
                  children: (
                    <pre className="raw-detail">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ),
                },
              ]}
            />
          </>
        )
      }
    />
  );
}

export function RuleReachabilityResult({ result }: { result: Result }) {
  const [offset, setOffset] = useState(0);
  const [detail, setDetail] = useState<Row | null>(null);
  const query = useRows(result, offset, "acl-rule-rows");
  const rows = query.data?.rows ?? [];
  const partial =
    result.truncated ||
    query.data?.truncated ||
    (query.data?.total ?? 0) > rows.length;
  return (
    <Card title="ACL 规则诊断">
      <Scope result={result} search={false} />
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !query.isPending ? (
        <Alert
          className="action-bar"
          type="warning"
          title={
            rows.length
              ? "发现模型判定不可达的规则；原因可能不同，请逐条核对。"
              : "当前范围未发现不可达规则；不能据此证明策略安全。"
          }
          description={
            partial
              ? "结果分页中或已截断；当前页不足以汇总整个范围。"
              : undefined
          }
        />
      ) : null}
      <Table<Row & { _key: string }>
        rowKey="_key"
        loading={query.isPending}
        dataSource={rows.map((row, index) => ({
          ...row,
          _key: result.id + ":" + (offset + index),
        }))}
        locale={{ emptyText: "当前范围无不可达规则；结论未知。" }}
        pagination={{
          current: offset / 20 + 1,
          pageSize: 20,
          total: query.data?.total,
          showSizeChanger: false,
          onChange: (page) => setOffset((page - 1) * 20),
        }}
        columns={[
          {
            title: "不可达规则",
            key: "line",
            render: (_, row) => cellText(row.Unreachable_Line),
          },
          {
            title: "原因",
            key: "reason",
            render: (_, row) => reachabilityReason(row).label,
          },
          {
            title: "阻挡规则",
            key: "blocking",
            render: (_, row) =>
              Array.isArray(row.Blocking_Lines) && row.Blocking_Lines.length
                ? row.Blocking_Lines.map(cellText).join("；")
                : "没有阻挡规则证据",
          },
          {
            title: "详情",
            key: "detail",
            render: (_, row) => (
              <Button type="link" onClick={() => setDetail(row)}>
                查看证据
              </Button>
            ),
          },
        ]}
      />
      <RawDetail
        result={result}
        row={detail}
        onClose={() => setDetail(null)}
        title="规则诊断详情"
        items={
          detail
            ? [
                {
                  key: "reason",
                  label: "模型原因",
                  children: reachabilityReason(detail).label,
                },
                {
                  key: "blocking",
                  label: "阻挡规则",
                  children:
                    Array.isArray(detail.Blocking_Lines) &&
                    detail.Blocking_Lines.length ? (
                      <pre className="raw-detail">
                        {JSON.stringify(detail.Blocking_Lines, null, 2)}
                      </pre>
                    ) : (
                      "没有阻挡规则证据"
                    ),
                },
                {
                  key: "source",
                  label: "来源证据",
                  children: detail.Sources ? (
                    <pre className="raw-detail">
                      {JSON.stringify(detail.Sources, null, 2)}
                    </pre>
                  ) : (
                    "没有可用来源证据"
                  ),
                },
              ]
            : []
        }
      />
    </Card>
  );
}
