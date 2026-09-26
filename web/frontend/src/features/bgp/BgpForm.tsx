import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Form, Select } from "antd";
import { useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, ApiError, unwrap } from "../../api/client";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { ErrorState } from "../../components/States";
import { useDraftGuard } from "../../components/useDraftGuard";
import { SelectorInput } from "../inventory/SelectorInput";
import { useCandidates } from "../inventory/useCandidates";
import { selectorValue } from "../routing/requests";

type Request = components["schemas"]["BgpRequest"];
type Mode = components["schemas"]["BgpOptions"]["mode"];
const blank = () => ({
  nodeMode: "literal" as "literal" | "expression",
  nodes: [] as string[],
  nodeExpression: "",
  remoteMode: "literal" as "literal" | "expression",
  remoteNodes: [] as string[],
  remoteExpression: "",
});
export function BgpForm({
  networkId,
  snapshotId,
  initialMode = "status",
}: {
  networkId: string;
  snapshotId: string;
  initialMode?: Mode;
}) {
  const navigate = useNavigate();
  const candidates = useCandidates(networkId, snapshotId);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [draft, setDraft] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<unknown>();
  const flight = useRef(false);
  const alive = useRef(true);
  const attempt = useRef<{ key: string; body: Request } | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const guard = useDraftGuard(
    locked ||
      mode !== initialMode ||
      JSON.stringify(draft) !== JSON.stringify(blank()),
    busy,
  );
  const update = <K extends keyof ReturnType<typeof blank>>(
    key: K,
    value: ReturnType<typeof blank>[K],
  ) => setDraft((old) => ({ ...old, [key]: value }));
  const nodes = selectorValue(
    draft.nodeMode,
    draft.nodes,
    draft.nodeExpression,
  );
  const remote = selectorValue(
    draft.remoteMode,
    draft.remoteNodes,
    draft.remoteExpression,
  );
  async function submit() {
    if (flight.current) return;
    attempt.current ??= {
      key: crypto.randomUUID(),
      body: { options: { mode, nodes, remote_nodes: remote } },
    };
    flight.current = true;
    setBusy(true);
    setLocked(true);
    setError(undefined);
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/bgp-sessions",
          {
            params: {
              path: { network_id: networkId, snapshot_id: snapshotId },
              header: { "idempotency-key": attempt.current.key },
            },
            body: attempt.current.body,
          },
        ),
      );
      if (alive.current) {
        guard.allowNavigation();
        navigate(`/jobs/${job.id}`);
      }
    } catch (caught) {
      if (alive.current) {
        setError(caught);
        if (
          caught instanceof ApiError &&
          [
            "VALIDATION_ERROR",
            "FORBIDDEN",
            "NOT_READY",
            "RATE_LIMITED",
            "NOT_FOUND",
            "CONFLICT",
          ].includes(caught.code)
        ) {
          attempt.current = null;
          setLocked(false);
        }
      }
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <Card title="BGP 会话分析条件">
      {guard.holder}
      {error != null && <ErrorState error={error} />}
      <Alert
        type="info"
        title="模型计算，非实时设备状态；成功建模也不能证明现场会话健康。"
      />
      <Form layout="vertical" disabled={busy || locked}>
        <Form.Item label="分析模式">
          <Select
            aria-label="BGP 分析模式"
            value={mode}
            virtual={false}
            onChange={setMode}
            options={[
              { value: "status", label: "模型状态" },
              { value: "compatibility", label: "配置兼容性" },
            ]}
          />
        </Form.Item>
        <AdvancedOptions activeCount={Number(!!nodes) + Number(!!remote)}>
          {candidates.controls}
          <SelectorInput
            label="本地设备"
            options={candidates.nodes}
            mode={draft.nodeMode}
            names={draft.nodes}
            expression={draft.nodeExpression}
            onMode={(v) => update("nodeMode", v)}
            onNames={(v) => update("nodes", v)}
            onExpression={(v) => update("nodeExpression", v)}
          />
          <SelectorInput
            label="远端设备"
            options={candidates.nodes}
            mode={draft.remoteMode}
            names={draft.remoteNodes}
            expression={draft.remoteExpression}
            onMode={(v) => update("remoteMode", v)}
            onNames={(v) => update("remoteNodes", v)}
            onExpression={(v) => update("remoteExpression", v)}
          />
        </AdvancedOptions>
      </Form>
      <Button
        type="primary"
        className="action-bar"
        loading={busy}
        onClick={() => void submit()}
      >
        {locked ? "重试 BGP 提交" : "分析 BGP 会话"}
      </Button>
    </Card>
  );
}
