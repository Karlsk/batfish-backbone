import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Space,
  Typography,
} from "antd";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useResourceContext } from "../../app/context";
import { api, ApiError, unwrap } from "../../api/client";
import { useDraftGuard } from "../../components/useDraftGuard";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { EmptyState, ErrorState } from "../../components/States";
import { useCandidates } from "../inventory/useCandidates";
import { traceProtocols, traceDefaults } from "../inventory/catalog";
import {
  buildTrace,
  defaultTrace,
  traceFromAcl,
  type TraceDraft,
} from "./requests";
export function TracePage() {
  const { network, snapshot } = useResourceContext();
  const location = useLocation();
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
  return (
    <TraceForm
      key={`${network.id}:${snapshot.id}`}
      networkId={network.id}
      snapshotId={snapshot.id}
      name={snapshot.name}
      presetFlow={
        (location.state as { presetFlow?: unknown } | null)?.presetFlow
      }
    />
  );
}
function TraceForm({
  networkId,
  snapshotId,
  name,
  presetFlow,
}: {
  networkId: string;
  snapshotId: string;
  name: string;
  presetFlow?: unknown;
}) {
  const [draft, setDraft] = useState(() =>
      traceFromAcl(presetFlow, networkId, snapshotId),
    ),
    [busy, setBusy] = useState(false),
    [attempted, setAttempted] = useState(false),
    [error, setError] = useState<unknown>(),
    [validation, setValidation] = useState("");
  const flight = useRef(false),
    alive = useRef(true),
    attempt = useRef<{ key: string; draft: TraceDraft } | null>(null);
  const navigate = useNavigate();
  const candidates = useCandidates(networkId, snapshotId);
  const guard = useDraftGuard(
    attempted || JSON.stringify(draft) !== JSON.stringify(defaultTrace()),
    busy,
  );
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const update = <K extends keyof TraceDraft>(k: K, v: TraceDraft[K]) =>
    setDraft((d) => ({ ...d, [k]: v }));
  async function submit() {
    if (flight.current) return;
    setValidation("");
    setError(undefined);
    try {
      buildTrace(draft);
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
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/traceroute",
          {
            params: {
              path: { network_id: networkId, snapshot_id: snapshotId },
              header: { "idempotency-key": attempt.current.key },
            },
            body: buildTrace(attempt.current.draft),
          },
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
  const count =
    Number(!!draft.source) +
    Number(
      JSON.stringify(draft.protocols) !==
        JSON.stringify(traceDefaults.ip_protocols),
    ) +
    Number(!!draft.sourcePorts) +
    Number(!!draft.ports) +
    Number(draft.maxTraces !== traceDefaults.max_traces) +
    Number(draft.ignoreFilters);
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>虚拟 traceroute</Typography.Title>
          <p className="muted">
            根据配置推演单向路径，不是在线 ping，也不证明回程连通。
          </p>
        </div>
        <Link to="/analysis/nodes">
          <Button>设备与路由</Button>
        </Link>
      </div>
      <Card title="起点与目标">
        {guard.holder}
        <p className="record-id">
          来源快照：{name} · {snapshotId}
        </p>
        {candidates.controls}
        {!!error && <ErrorState error={error} />}{" "}
        {validation && <Alert type="error" title={validation} />}{" "}
        {attempted && !busy && !!error && (
          <Alert
            type="info"
            title="提交结果尚未确认；重试保留原参数和请求标识。"
          />
        )}
        <Form layout="vertical" disabled={busy || attempted}>
          <Form.Item label="起点输入方式">
            <Radio.Group
              value={draft.mode}
              onChange={(e) => update("mode", e.target.value)}
              options={[
                { label: "设备与接口", value: "literal" },
                { label: "专家表达式", value: "expression" },
              ]}
            />
          </Form.Item>
          {draft.mode === "literal" ? (
            <>
              <Form.Item label="起点设备">
                <Select
                  aria-label="起点设备"
                  showSearch
                  virtual={false}
                  value={draft.node || undefined}
                  options={candidates.nodes.map((value) => ({
                    value,
                    label: value,
                  }))}
                  placeholder="先加载当前快照候选"
                  onChange={(v) =>
                    setDraft((d) => ({ ...d, node: v, iface: "" }))
                  }
                />
              </Form.Item>
              <Form.Item label="起点接口（可选）">
                <Select
                  aria-label="起点接口"
                  allowClear
                  showSearch
                  virtual={false}
                  value={draft.iface || undefined}
                  disabled={!draft.node || busy || attempted}
                  options={candidates
                    .interfaces([draft.node])
                    .map((value) => ({ value, label: value }))}
                  placeholder="留空使用设备的可用起点"
                  onChange={(v) => update("iface", v ?? "")}
                />
              </Form.Item>
            </>
          ) : (
            <Form.Item label="起点表达式">
              <Input
                aria-label="起点表达式"
                value={draft.expression}
                onChange={(e) => update("expression", e.target.value)}
                placeholder="Batfish startLocation，如 c1,c2"
              />
            </Form.Item>
          )}
          <Form.Item label="目标 IPv4 地址">
            <Input
              aria-label="目标 IPv4 地址"
              value={draft.destination}
              onChange={(e) => update("destination", e.target.value)}
              placeholder="如 10.64.0.4"
            />
          </Form.Item>
          <AdvancedOptions activeCount={count}>
            <Form.Item label="源 IPv4 地址（可选）">
              <Input
                aria-label="源 IPv4 地址"
                value={draft.source}
                onChange={(e) => update("source", e.target.value)}
                placeholder="留空由模型根据起点推导"
              />
            </Form.Item>
            <Form.Item label="IP 协议">
              <Select
                aria-label="IP 协议"
                mode="multiple"
                virtual={false}
                value={draft.protocols}
                options={traceProtocols.map((value) => ({
                  value,
                  label: value.toUpperCase(),
                }))}
                onChange={(v) => update("protocols", v)}
              />
            </Form.Item>
            <Form.Item label="源端口（可选）">
              <Input
                aria-label="源端口"
                value={draft.sourcePorts}
                onChange={(e) => update("sourcePorts", e.target.value)}
                placeholder="TCP/UDP端口，逗号分隔"
              />
            </Form.Item>
            <Form.Item label="目标端口（可选）">
              <Input
                aria-label="目标端口"
                value={draft.ports}
                onChange={(e) => update("ports", e.target.value)}
                placeholder="TCP/UDP端口，逗号分隔"
              />
            </Form.Item>
            <Form.Item label="每个 Flow 最多展示路径数">
              <InputNumber
                aria-label="最多路径数"
                min={1}
                max={20}
                value={draft.maxTraces}
                onChange={(v) => update("maxTraces", v ?? 0)}
              />
            </Form.Item>
            <Checkbox
              checked={draft.ignoreFilters}
              onChange={(e) => update("ignoreFilters", e.target.checked)}
            >
              忽略 ACL 过滤规则
            </Checkbox>
          </AdvancedOptions>
        </Form>
        {draft.ignoreFilters && (
          <Alert
            className="summary-warning"
            type="warning"
            showIcon
            title="本次推演将忽略 ACL 过滤规则，不能据此判断访问策略允许。"
          />
        )}
        <Button
          className="action-bar"
          type="primary"
          loading={busy}
          onClick={() => void submit()}
        >
          {attempted ? "重试提交" : "推演路径"}
        </Button>
      </Card>
    </>
  );
}
