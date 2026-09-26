import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Input,
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
import { BgpForm } from "./BgpForm";

type Result = components["schemas"]["ResultEnvelope"];
type Row = Record<string, unknown>;
function name(value: unknown): string | null {
  if (typeof value === "string") return value || null;
  if (value && typeof value === "object") {
    const object = value as Row;
    if (typeof object.name === "string") return object.name || null;
    if (typeof object.hostname === "string") return object.hostname || null;
  }
  return null;
}
function resultMode(result: Result) {
  const request = result.effective_parameters.request;
  const options =
    request && typeof request === "object" && !Array.isArray(request)
      ? (request as Row).options
      : null;
  return options &&
    typeof options === "object" &&
    !Array.isArray(options) &&
    (options as Row).mode === "compatibility"
    ? "compatibility"
    : "status";
}
export function BgpResult({ result }: { result: Result }) {
  const session = useSession();
  const selection = useResourceContext();
  const navigate = useNavigate();
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const mode = resultMode(result);
  const statusColumn =
    mode === "status" ? "Established_Status" : "Configured_Status";
  const [offset, setOffset] = useState(0);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("");
  const [detail, setDetail] = useState<Row | null>(null);
  const [navigationError, setNavigationError] = useState<unknown>();
  const [navigating, setNavigating] = useState(false);
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
  const params = {
    offset,
    limit: 20,
    ...(status
      ? {
          filters: JSON.stringify([
            { column: statusColumn, op: "eq", value: status },
          ]),
        }
      : {}),
  };
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "bgp-rows",
      params,
      result.id,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/rows", {
          signal,
          params: { path: { result_id: result.id }, query: params },
        }),
      ),
  });
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
                snapshot_id: context.snapshotId,
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
    } catch (caught) {
      if (current()) setNavigationError(caught);
    } finally {
      if (current()) {
        routeInFlight.current = false;
        setNavigating(false);
      }
    }
  }
  const columns = query.data?.columns.map((column) => column.key) ?? [];
  return (
    <Card title={mode === "status" ? "BGP 模型状态会话" : "BGP 配置兼容性分析"}>
      <Alert
        type="info"
        title="模型计算，非实时设备状态；结果来自固定快照，不能作为现场会话健康告警。"
        description={
          <Link
            to={`/networks/${context.networkId}/snapshots/${context.snapshotId}/diagnostics`}
          >
            查看快照解析与模型限制
          </Link>
        }
      />
      <Collapse
        className="action-bar"
        items={[
          {
            key: "new-analysis",
            label: "切换分析模式或高级条件（生成新结果）",
            children: (
              <BgpForm
                key={result.id}
                networkId={context.networkId}
                snapshotId={context.snapshotId}
                initialMode={mode}
              />
            ),
          },
        ]}
      />
      <Space wrap className="filter-bar">
        <Input
          aria-label="原始状态筛选"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入完整原始状态；留空显示全部"
          style={{ width: 270 }}
          disabled={!columns.includes(statusColumn)}
        />
        <Button
          onClick={() => {
            setStatus(input.trim());
            setOffset(0);
          }}
          disabled={!columns.includes(statusColumn)}
        >
          应用状态筛选
        </Button>
        {status && (
          <Button
            onClick={() => {
              setInput("");
              setStatus("");
              setOffset(0);
            }}
          >
            清除状态筛选
          </Button>
        )}
        {status && <span>生效状态：{status}</span>}
      </Space>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <Table<Row & { _key: string }>
          rowKey="_key"
          loading={query.isPending}
          dataSource={query.data?.rows.map((row, index) => ({
            ...row,
            _key: `${result.id}:${offset + index}`,
          }))}
          scroll={{ x: 620 }}
          locale={{
            emptyText: query.isPending
              ? "正在读取会话"
              : "此快照没有匹配的 BGP 会话；空结果不代表现场会话正常。",
          }}
          pagination={{
            current: offset / 20 + 1,
            pageSize: 20,
            total: query.data?.total,
            showSizeChanger: false,
            onChange: (page) => setOffset((page - 1) * 20),
          }}
          columns={[
            {
              title: "本地设备",
              key: "local",
              render: (_, row) => (
                <Button
                  type="link"
                  aria-label="查看会话详情"
                  onClick={() => {
                    const { _key, ...raw } = row;
                    setDetail(raw);
                  }}
                >
                  {name(row.Node) ?? "本地未知"}
                </Button>
              ),
            },
            {
              title: "远端设备",
              key: "remote",
              render: (_, row) => name(row.Remote_Node) ?? "远端未知",
            },
            {
              title: "远端地址",
              key: "remoteIp",
              render: (_, row) => cellText(row.Remote_IP),
            },
            {
              title: mode === "status" ? "原始模型状态" : "原始兼容状态",
              key: "status",
              render: (_, row) => (
                <Tag
                  color={
                    String(row[statusColumn]).includes("NOT_") ||
                    String(row[statusColumn]).includes("NO_")
                      ? "orange"
                      : "blue"
                  }
                >
                  {cellText(row[statusColumn])}
                </Tag>
              ),
            },
          ]}
        />
      )}
      {navigationError != null && <ErrorState error={navigationError} />}
      <DetailsDrawer
        open={!!detail}
        title="BGP 会话详情"
        onClose={() => setDetail(null)}
        queryKey={resourceKey(
          session?.user_id ?? null,
          context,
          "bgp-detail",
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
                    key: "local",
                    label: "本地设备",
                    children: name(row.Node) ?? "本地未知",
                  },
                  {
                    key: "remote",
                    label: "远端设备",
                    children: name(row.Remote_Node) ?? "远端未知",
                  },
                  {
                    key: "addresses",
                    label: "本地 / 远端地址",
                    children: `${cellText(row.Local_IP)} / ${cellText(row.Remote_IP)}`,
                  },
                  {
                    key: "localInterface",
                    label: "本地接口",
                    children: cellText(row.Local_Interface),
                  },
                  {
                    key: "remoteInterface",
                    label: "远端接口",
                    children: cellText(row.Remote_Interface),
                  },
                  {
                    key: "vrf",
                    label: "本地 / 会话 VRF",
                    children: `${cellText(row.VRF)} / ${cellText(row.Session_VRF)}`,
                  },
                  {
                    key: "as",
                    label: "本地 / 远端 AS",
                    children: `${cellText(row.Local_AS)} / ${cellText(row.Remote_AS)}`,
                  },
                  {
                    key: "families",
                    label: "地址族",
                    children: cellText(row.Address_Families),
                  },
                  {
                    key: "status",
                    label: "原始状态",
                    children: cellText(row[statusColumn]),
                  },
                ]}
              />
              <Space wrap className="action-bar">
                {name(row.Node) && (
                  <Button
                    loading={navigating}
                    onClick={() => void routes(name(row.Node)!)}
                  >
                    查询本地设备路由
                  </Button>
                )}
                {name(row.Remote_Node) && (
                  <Button
                    loading={navigating}
                    onClick={() => void routes(name(row.Remote_Node)!)}
                  >
                    查询远端设备路由
                  </Button>
                )}
              </Space>
              <Collapse
                items={[
                  {
                    key: "raw",
                    label: "原始 SDK 属性",
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
