import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Space,
  Table,
  Tag,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, unwrap } from "../../api/client";
import { resourceKey, useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import { ErrorState } from "../../components/States";
import { cellText } from "../results/cells";

type Result = components["schemas"]["ResultEnvelope"];
type Row = Record<string, unknown>;
type Decision = {
  kind: "allow" | "deny" | "unknown" | "mixed";
  implicit: boolean;
  label: string;
};

export function aclDecision(
  rows: Row[],
  total = rows.length,
  truncated = false,
): Decision {
  if (truncated || total > rows.length)
    return {
      kind: "unknown",
      implicit: false,
      label: "结果分页中，请逐项查看 ACL 动作",
    };
  if (!rows.length)
    return {
      kind: "unknown",
      implicit: false,
      label: "没有匹配的 ACL，无法判断",
    };
  const actions = rows.map((row) => row.Action);
  if (actions.some((action) => action !== "PERMIT" && action !== "DENY"))
    return { kind: "unknown", implicit: false, label: "模型未给出可判定动作" };
  if (new Set(actions).size > 1)
    return { kind: "mixed", implicit: false, label: "不同 ACL 的动作不一致" };
  if (actions[0] === "PERMIT")
    return { kind: "allow", implicit: false, label: "ACL 局部放行" };
  const implicit = rows.every((row) => row.Implicit_Deny === true);
  return {
    kind: "deny",
    implicit,
    label: implicit ? "隐式拒绝" : "ACL 拒绝",
  };
}

function nodeName(value: unknown) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "name" in value)
    return String(value.name);
  return "未知设备";
}

export function FilterResult({ result }: { result: Result }) {
  const session = useSession();
  const selection = useResourceContext();
  const navigate = useNavigate();
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const [offset, setOffset] = useState(0);
  const [detail, setDetail] = useState<Row | null>(null);
  const [navigationError, setNavigationError] = useState<unknown>();
  const [navigating, setNavigating] = useState(false);
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "acl-rows",
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
  const rows = query.data?.rows ?? [];
  const decision = aclDecision(
    rows,
    query.data?.total ?? rows.length,
    query.data?.truncated,
  );
  async function trace() {
    if (navigating) return;
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
                snapshot_id: context.snapshotId,
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
      const request = result.effective_parameters.request as
        | Record<string, unknown>
        | undefined;
      navigate("/traceroute", {
        state: {
          presetFlow: {
            ...context,
            source: request?.source_ip,
            destination: request?.destination_ip,
            options: request?.options,
          },
        },
      });
    } catch (error) {
      setNavigationError(error);
    } finally {
      setNavigating(false);
    }
  }
  return (
    <Card title="ACL 流量测试">
      <Alert
        type="info"
        title="这是配置模型对指定 ACL 的局部判断，不代表端到端可达或现场转发。"
        description={
          <Link
            to={`/networks/${context.networkId}/snapshots/${context.snapshotId}/diagnostics`}
          >
            查看快照解析与模型限制
          </Link>
        }
      />
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !query.isPending ? (
        <Alert
          className="action-bar"
          type={
            decision.kind === "allow"
              ? "success"
              : decision.kind === "deny"
                ? "error"
                : "warning"
          }
          title={decision.label}
          description={
            query.data?.truncated
              ? "结果已截断；这里只展示当前页，不能据此汇总所有 ACL。"
              : undefined
          }
        />
      ) : null}
      <Table<Row & { _key: string }>
        rowKey="_key"
        loading={query.isPending}
        dataSource={rows.map((row, index) => ({
          ...row,
          _key: `${result.id}:${offset + index}`,
        }))}
        locale={{ emptyText: "没有匹配的 ACL；不能据此判断放行。" }}
        pagination={{
          current: offset / 20 + 1,
          pageSize: 20,
          total: query.data?.total,
          showSizeChanger: false,
          onChange: (page) => setOffset((page - 1) * 20),
        }}
        columns={[
          {
            title: "设备",
            key: "node",
            render: (_, row) => nodeName(row.Node),
          },
          {
            title: "ACL",
            key: "filter",
            render: (_, row) => cellText(row.Filter_Name),
          },
          {
            title: "局部动作",
            key: "action",
            render: (_, row) => {
              const value = aclDecision([row]);
              return (
                <Tag
                  color={
                    value.kind === "allow"
                      ? "green"
                      : value.kind === "deny"
                        ? "red"
                        : "orange"
                  }
                >
                  {value.label}
                </Tag>
              );
            },
          },
          {
            title: "命中依据",
            key: "evidence",
            render: (_, row) =>
              row.Implicit_Deny === true
                ? "没有匹配规则（隐式拒绝）"
                : cellText(row.Line_Content),
          },
          {
            title: "详情",
            key: "detail",
            render: (_, row) => (
              <Button
                type="link"
                onClick={() => {
                  const { _key, ...raw } = row;
                  setDetail(raw);
                }}
              >
                查看证据
              </Button>
            ),
          },
        ]}
      />
      <Space wrap className="action-bar">
        <Button onClick={() => void trace()} loading={navigating}>
          继续分析路径（需选择起点）
        </Button>
      </Space>
      {navigationError != null && <ErrorState error={navigationError} />}
      <DetailsDrawer
        open={!!detail}
        title="ACL 命中详情"
        onClose={() => setDetail(null)}
        queryKey={resourceKey(
          session?.user_id ?? null,
          context,
          "acl-detail",
          detail,
          result.id,
        )}
        load={async () => detail}
        render={(row) =>
          row && (
            <>
              <Descriptions
                column={1}
                bordered
                size="small"
                items={[
                  {
                    key: "action",
                    label: "动作",
                    children: aclDecision([row]).label,
                  },
                  {
                    key: "line",
                    label: "规则内容",
                    children:
                      row.Implicit_Deny === true
                        ? "没有匹配规则（隐式拒绝）"
                        : cellText(row.Line_Content),
                  },
                  {
                    key: "flow",
                    label: "实际 Flow",
                    children: (
                      <pre className="raw-detail">
                        {JSON.stringify(row.Flow, null, 2)}
                      </pre>
                    ),
                  },
                  {
                    key: "source",
                    label: "配置来源",
                    children:
                      Array.isArray(row.Source_References) &&
                      row.Source_References.length ? (
                        <pre className="raw-detail">
                          {JSON.stringify(row.Source_References, null, 2)}
                        </pre>
                      ) : (
                        "没有可用来源引用"
                      ),
                  },
                ]}
              />
              <Collapse
                items={[
                  {
                    key: "raw",
                    label: "原始 SDK 证据",
                    children: (
                      <pre className="raw-detail">
                        {JSON.stringify(row, null, 2)}
                      </pre>
                    ),
                  },
                ]}
              />
            </>
          )
        }
      />
    </Card>
  );
}
