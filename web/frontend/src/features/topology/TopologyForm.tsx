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
import { views } from "./model";
type Request = components["schemas"]["TopologyRequest"];
const empty = () => ({
  mode: "literal" as "literal" | "expression",
  names: [] as string[],
  expression: "",
  remoteMode: "literal" as "literal" | "expression",
  remoteNames: [] as string[],
  remoteExpression: "",
});
export function TopologyForm({
  networkId,
  snapshotId,
  initialView = "layer3",
}: {
  networkId: string;
  snapshotId: string;
  initialView?: Request["view"];
}) {
  const navigate = useNavigate(),
    candidates = useCandidates(networkId, snapshotId);
  const [view, setView] = useState(initialView),
    [draft, setDraft] = useState(empty),
    [busy, setBusy] = useState(false),
    [locked, setLocked] = useState(false),
    [error, setError] = useState<unknown>();
  const flight = useRef(false),
    alive = useRef(true),
    attempt = useRef<{ key: string; body: Request } | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const guard = useDraftGuard(
    locked ||
      view !== initialView ||
      JSON.stringify(draft) !== JSON.stringify(empty()),
    busy,
  );
  const update = <K extends keyof ReturnType<typeof empty>>(
    key: K,
    value: ReturnType<typeof empty>[K],
  ) => setDraft((old) => ({ ...old, [key]: value }));
  async function submit() {
    if (flight.current) return;
    attempt.current ??= {
      key: crypto.randomUUID(),
      body: {
        view,
        options: {
          nodes: selectorValue(draft.mode, draft.names, draft.expression),
          remote_nodes: selectorValue(
            draft.remoteMode,
            draft.remoteNames,
            draft.remoteExpression,
          ),
        },
      },
    };
    flight.current = true;
    setBusy(true);
    setLocked(true);
    setError(undefined);
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/topology",
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
    } catch (error) {
      if (alive.current) {
        setError(error);
        if (
          error instanceof ApiError &&
          [
            "VALIDATION_ERROR",
            "FORBIDDEN",
            "NOT_READY",
            "RATE_LIMITED",
            "NOT_FOUND",
            "CONFLICT",
          ].includes(error.code)
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
    <Card title="拓扑分析条件">
      {guard.holder}
      {error != null && <ErrorState error={error} />}
      <Alert
        type="info"
        title="来自配置模型的关系，不代表实时链路通断或协议会话健康。"
      />
      <Form layout="vertical" disabled={busy || locked}>
        <Form.Item label="关系视图">
          <Select
            aria-label="关系视图"
            virtual={false}
            value={view}
            onChange={setView}
            options={Object.entries(views).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </Form.Item>
        <AdvancedOptions
          activeCount={
            Number(!!selectorValue(draft.mode, draft.names, draft.expression)) +
            Number(
              !!selectorValue(
                draft.remoteMode,
                draft.remoteNames,
                draft.remoteExpression,
              ),
            )
          }
        >
          {candidates.controls}
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
          <SelectorInput
            label="邻居设备"
            options={candidates.nodes}
            mode={draft.remoteMode}
            names={draft.remoteNames}
            expression={draft.remoteExpression}
            onMode={(v) => update("remoteMode", v)}
            onNames={(v) => update("remoteNames", v)}
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
        {locked ? "重试拓扑提交" : "生成拓扑"}
      </Button>
    </Card>
  );
}
