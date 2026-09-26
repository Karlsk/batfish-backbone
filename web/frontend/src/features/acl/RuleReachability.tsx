import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Alert, Button, Card, Checkbox, Form } from "antd";
import { useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, ApiError, unwrap } from "../../api/client";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { ErrorState } from "../../components/States";
import { useDraftGuard } from "../../components/useDraftGuard";
import {
  buildRuleReachability,
  defaultReachabilityDraft,
  type ReachabilityDraft,
} from "./advanced-requests";
import {
  AdvancedScope,
  CapabilityState,
  useAclCapability,
} from "./AdvancedScope";

type Request = components["schemas"]["FilterLineReachabilityRequest"];

export function RuleReachability({
  networkId,
  snapshotId,
  draftValue,
  onDraftChange,
  onLockChange,
}: {
  networkId: string;
  snapshotId: string;
  draftValue?: ReachabilityDraft;
  onDraftChange?: Dispatch<SetStateAction<ReachabilityDraft>>;
  onLockChange?: (locked: boolean) => void;
}) {
  const navigate = useNavigate();
  const { query, capability } = useAclCapability("filter-line-reachability");
  const [ownDraft, setOwnDraft] = useState(defaultReachabilityDraft);
  const draft = draftValue ?? ownDraft;
  const setDraft = onDraftChange ?? setOwnDraft;
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [validation, setValidation] = useState("");
  const [error, setError] = useState<unknown>();
  const alive = useRef(true);
  const flight = useRef(false);
  const attempt = useRef<{ key: string; body: Request } | null>(null);
  const defaultApplied = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    const defaults = capability?.defaults?.options;
    if (
      !defaultApplied.current &&
      defaults &&
      typeof defaults === "object" &&
      !Array.isArray(defaults) &&
      "ignore_composites" in defaults &&
      typeof defaults.ignore_composites === "boolean"
    ) {
      defaultApplied.current = true;
      const ignoreComposites = defaults.ignore_composites;
      setDraft((old) => ({
        ...old,
        ignoreComposites,
      }));
    }
  }, [capability]);
  const guard = useDraftGuard(
    locked ||
      JSON.stringify(draft) !== JSON.stringify(defaultReachabilityDraft()),
    busy,
  );
  const update = <K extends keyof ReachabilityDraft>(
    key: K,
    value: ReachabilityDraft[K],
  ) => setDraft((old) => ({ ...old, [key]: value }));
  async function submit() {
    if (flight.current || !capability?.enabled) return;
    setValidation("");
    let body: Request;
    try {
      body = buildRuleReachability(draft);
    } catch (caught) {
      setValidation((caught as Error).message);
      return;
    }
    attempt.current ??= { key: crypto.randomUUID(), body };
    flight.current = true;
    setBusy(true);
    setLocked(true);
    onLockChange?.(true);
    setError(undefined);
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/filter-line-reachability",
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
          onLockChange?.(false);
        }
      }
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <Card title="诊断 ACL 无法命中的规则">
      {guard.holder}
      <Alert
        type="info"
        title="不可达规则可能是被前序规则阻挡，也可能是条件本身无法匹配。"
      />
      <CapabilityState query={query} capability={capability} />
      {error != null && <ErrorState error={error} />}
      {validation && <Alert type="error" title={validation} />}
      {locked && !busy && error != null && (
        <Alert type="info" title="提交状态未知；重试保留原参数和请求标识。" />
      )}
      <Form layout="vertical" disabled={busy || locked || !capability?.enabled}>
        <AdvancedScope
          networkId={networkId}
          snapshotId={snapshotId}
          nodes={draft.nodes}
          filters={draft.filters}
          onNodes={(value) => update("nodes", value)}
          onFilters={(value) => update("filters", value)}
        />
        <AdvancedOptions activeCount={Number(!draft.ignoreComposites)}>
          <Form.Item label="复合规则">
            <Checkbox
              checked={draft.ignoreComposites}
              onChange={(event) =>
                update("ignoreComposites", event.target.checked)
              }
            >
              忽略复合规则（SDK 默认）
            </Checkbox>
          </Form.Item>
        </AdvancedOptions>
      </Form>
      <Button
        className="action-bar"
        type="primary"
        loading={busy}
        disabled={!capability?.enabled}
        onClick={() => void submit()}
      >
        {locked ? "重试规则诊断提交" : "诊断不可达规则"}
      </Button>
    </Card>
  );
}
