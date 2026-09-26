import { useCandidates } from "./useCandidates";
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Typography,
  Form,
} from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, unwrap, ApiError } from "../../api/client";
import { useResourceContext } from "../../app/context";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { EmptyState, ErrorState } from "../../components/States";
import { useDraftGuard } from "../../components/useDraftGuard";
import {
  buildRequest,
  defaultDraft,
  type Draft,
  type Operation,
} from "../routing/requests";
import { SelectorInput } from "./SelectorInput";
import { nodeProperties, interfaceProperties, protocols } from "./catalog";
export const operationLabels: Record<Operation, string> = {
  nodes: "设备",
  interfaces: "接口",
  routes: "路由前缀",
  "lpm-routes": "最长前缀匹配",
};
export function AnalysisPage() {
  const { network, snapshot } = useResourceContext();
  const { operation = "nodes" } = useParams();
  if (!network || !snapshot)
    return (
      <EmptyState
        title="请先选择网络与就绪快照"
        action={
          <Link to="/snapshots">
            <Button>选择快照</Button>
          </Link>
        }
      />
    );
  if (!Object.hasOwn(operationLabels, operation))
    return <EmptyState title="此分析尚未开放" />;
  return (
    <>
      <Typography.Title level={2}>网络分析</Typography.Title>
      <Space wrap className="filter-bar analysis-tabs">
        {Object.entries(operationLabels).map(([key, label]) => (
          <Link key={key} to={`/analysis/${key}`}>
            <Button type={key === operation ? "primary" : "default"}>
              {label}
            </Button>
          </Link>
        ))}
        <Link to="/traceroute">
          <Button>虚拟 traceroute</Button>
        </Link>
      </Space>
      <AnalysisForm
        key={`${network.id}:${snapshot.id}:${operation}`}
        networkId={network.id}
        snapshotId={snapshot.id}
        name={snapshot.name}
        operation={operation as Operation}
      />
    </>
  );
}
function AnalysisForm({
  networkId,
  snapshotId,
  name,
  operation,
}: {
  networkId: string;
  snapshotId: string;
  name: string;
  operation: Operation;
}) {
  const navigate = useNavigate();
  const candidates = useCandidates(networkId, snapshotId);
  const [draft, setDraft] = useState(defaultDraft);
  const [busy, setBusy] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState<unknown>();
  const [validation, setValidation] = useState("");
  const flight = useRef(false),
    alive = useRef(true);
  const attempt = useRef<{ key: string; draft: Draft } | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const guard = useDraftGuard(
    attempted || JSON.stringify(draft) !== JSON.stringify(defaultDraft()),
    busy,
  );
  const update = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((previous) => ({ ...previous, [key]: value }));
  const route = operation === "routes" || operation === "lpm-routes";
  const advancedCount =
    Number(draft.properties.length > 0) +
    Number(
      operation === "interfaces" &&
        (draft.interfaceMode === "literal"
          ? draft.interfaces.length > 0
          : !!draft.interfaceExpression),
    ) +
    Number(
      route &&
        (draft.vrfMode === "literal"
          ? draft.vrfs.length > 0
          : !!draft.vrfExpression),
    ) +
    Number(operation === "routes" && draft.protocols.length > 0) +
    Number(operation === "routes" && draft.rib !== "main") +
    Number(operation === "routes" && draft.prefixMatch !== "EXACT");
  async function submit() {
    if (flight.current) return;
    setValidation("");
    setError(undefined);
    try {
      buildRequest(operation, draft);
    } catch (e) {
      setValidation((e as Error).message);
      return;
    }
    attempt.current ??= {
      key: crypto.randomUUID(),
      draft: structuredClone(draft),
    };
    flight.current = true;
    setBusy(true);
    setAttempted(true);
    const params = {
      path: { network_id: networkId, snapshot_id: snapshotId },
      header: { "idempotency-key": attempt.current.key },
    };
    const frozen = attempt.current.draft;
    try {
      const job =
        operation === "nodes"
          ? await unwrap(
              api.POST(
                "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/nodes",
                { params, body: buildRequest("nodes", frozen) },
              ),
            )
          : operation === "interfaces"
            ? await unwrap(
                api.POST(
                  "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/interfaces",
                  { params, body: buildRequest("interfaces", frozen) },
                ),
              )
            : operation === "routes"
              ? await unwrap(
                  api.POST(
                    "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/routes",
                    { params, body: buildRequest("routes", frozen) },
                  ),
                )
              : await unwrap(
                  api.POST(
                    "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/lpm-routes",
                    { params, body: buildRequest("lpm-routes", frozen) },
                  ),
                );
      if (alive.current) {
        guard.allowNavigation();
        navigate(`/jobs/${job.id}`);
      }
    } catch (e) {
      if (alive.current) {
        setError(e);
        if (
          e instanceof ApiError &&
          [
            "VALIDATION_ERROR",
            "FORBIDDEN",
            "NOT_READY",
            "RATE_LIMITED",
          ].includes(e.code)
        ) {
          attempt.current = null;
          setAttempted(false);
        }
      }
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <Card className="analysis-form" title={`${operationLabels[operation]}查询`}>
      {guard.holder}
      <p className="record-id">
        来源快照：{name} · {snapshotId}
      </p>
      {error ? <ErrorState error={error} /> : null}
      {validation && <Alert type="error" title={validation} />}
      {attempted && !busy && !!error && (
        <Alert
          type="info"
          title="提交结果尚未确认；参数已保留，重试将使用同一请求标识。"
        />
      )}
      {candidates.controls}
      <Form layout="vertical" disabled={busy || attempted}>
        <SelectorInput
          label="设备"
          options={candidates.nodes}
          mode={draft.mode}
          names={draft.names}
          expression={draft.expression}
          onMode={(v) => update("mode", v)}
          onNames={(v) => update("names", v)}
          onExpression={(v) => update("expression", v)}
        />
        {route && (
          <Form.Item
            label={
              operation === "routes"
                ? "IPv4 路由前缀（可选）"
                : "目标 IPv4 地址"
            }
          >
            <Input
              aria-label={
                operation === "routes" ? "IPv4 路由前缀" : "目标 IPv4 地址"
              }
              value={draft.destination}
              onChange={(e) => update("destination", e.target.value)}
              placeholder={
                operation === "routes"
                  ? "如 10.0.0.0/24；留空查询全部"
                  : "如 10.0.0.1"
              }
            />
          </Form.Item>
        )}
        {operation === "lpm-routes" && (
          <Alert
            type="info"
            title="查询覆盖目标地址的最长前缀；结果为匹配摘要，不包含逐条下一跳。"
          />
        )}
        <AdvancedOptions activeCount={advancedCount}>
          {operation === "interfaces" && (
            <SelectorInput
              label="接口"
              options={candidates.interfaces(
                draft.mode === "literal" ? draft.names : [],
              )}
              mode={draft.interfaceMode}
              names={draft.interfaces}
              expression={draft.interfaceExpression}
              onMode={(v) => update("interfaceMode", v)}
              onNames={(v) => update("interfaces", v)}
              onExpression={(v) => update("interfaceExpression", v)}
            />
          )}
          {!route && (
            <Form.Item label="返回属性（留空使用默认值）">
              <Select
                aria-label="返回属性"
                mode="multiple"
                virtual={false}
                value={draft.properties}
                onChange={(v) => update("properties", v)}
                options={(operation === "nodes"
                  ? nodeProperties
                  : interfaceProperties
                ).map((value) => ({ value, label: value }))}
              />
            </Form.Item>
          )}
          {route && (
            <SelectorInput
              label="VRF"
              options={candidates.vrfs(
                draft.mode === "literal" ? draft.names : [],
              )}
              mode={draft.vrfMode}
              names={draft.vrfs}
              expression={draft.vrfExpression}
              onMode={(v) => update("vrfMode", v)}
              onNames={(v) => update("vrfs", v)}
              onExpression={(v) => update("vrfExpression", v)}
            />
          )}
          {operation === "routes" && (
            <>
              <Form.Item label="前缀匹配方式">
                <Select
                  aria-label="前缀匹配方式"
                  virtual={false}
                  value={draft.prefixMatch}
                  onChange={(v) => update("prefixMatch", v)}
                  options={[
                    { value: "EXACT", label: "精确前缀（EXACT）" },
                    {
                      value: "LONGEST_PREFIX_MATCH",
                      label: "最长前缀（LONGEST_PREFIX_MATCH）",
                    },
                    { value: "LONGER_PREFIXES", label: "更长前缀" },
                    { value: "SHORTER_PREFIXES", label: "更短前缀" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="路由表">
                <Select
                  aria-label="路由表"
                  virtual={false}
                  value={draft.rib}
                  onChange={(v) => update("rib", v)}
                  options={[
                    { value: "main", label: "主路由表" },
                    { value: "bgp", label: "BGP 路由表" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="路由协议">
                <Select
                  aria-label="路由协议"
                  mode="multiple"
                  virtual={false}
                  value={draft.protocols}
                  onChange={(v) => update("protocols", v)}
                  options={protocols.map((value) => ({ value, label: value }))}
                />
              </Form.Item>
            </>
          )}
        </AdvancedOptions>
      </Form>
      <Button
        className="action-bar"
        type="primary"
        loading={busy}
        onClick={() => void submit()}
      >
        {attempted ? "重试提交" : "执行查询"}
      </Button>
    </Card>
  );
}
