import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Alert, Button, Card, Form, Input, Select } from "antd";
import { useNavigate } from "react-router-dom";
import type { components } from "../../api/schema";
import { api, ApiError, unwrap } from "../../api/client";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { ErrorState } from "../../components/States";
import { useDraftGuard } from "../../components/useDraftGuard";
import { traceProtocols } from "../inventory/catalog";
import {
  buildFilterSearch,
  defaultSearchDraft,
  type SearchDraft,
} from "./advanced-requests";
import {
  AdvancedScope,
  CapabilityState,
  useAclCapability,
} from "./AdvancedScope";

type Request = components["schemas"]["SearchFiltersRequest"];

export function FilterSearch({
  networkId,
  snapshotId,
  draftValue,
  onDraftChange,
  onLockChange,
}: {
  networkId: string;
  snapshotId: string;
  draftValue?: SearchDraft;
  onDraftChange?: Dispatch<SetStateAction<SearchDraft>>;
  onLockChange?: (locked: boolean) => void;
}) {
  const navigate = useNavigate();
  const { query, capability } = useAclCapability("search-filters");
  const [ownDraft, setOwnDraft] = useState(defaultSearchDraft);
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
    const value = capability?.defaults?.action;
    if (
      !defaultApplied.current &&
      (value === "permit" || value === "deny" || value === "match_line")
    ) {
      defaultApplied.current = true;
      if (value !== "match_line")
        setDraft((old) => ({ ...old, action: value }));
    }
  }, [capability]);
  const guard = useDraftGuard(
    locked || JSON.stringify(draft) !== JSON.stringify(defaultSearchDraft()),
    busy,
  );
  const update = <K extends keyof SearchDraft>(key: K, value: SearchDraft[K]) =>
    setDraft((old) => ({ ...old, [key]: value }));
  async function submit() {
    if (flight.current || !capability?.enabled) return;
    setValidation("");
    let body: Request;
    try {
      body = buildFilterSearch(draft);
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
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/search-filters",
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
  const advancedCount =
    Number(draft.action !== "permit") +
    Number(draft.protocols.length > 0) +
    Number(!!draft.sourcePorts) +
    Number(!!draft.destinationPorts);
  return (
    <Card title="按条件寻找 ACL 示例流量">
      {guard.holder}
      <Alert
        type="warning"
        title="这里只寻找所选条件的示例流量；没有示例不代表策略安全。"
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
        <Form.Item label="源 IPv4 地址">
          <Input
            aria-label="搜索源 IPv4 地址"
            value={draft.source}
            onChange={(event) => update("source", event.target.value)}
          />
        </Form.Item>
        <Form.Item label="目标 IPv4 地址">
          <Input
            aria-label="搜索目标 IPv4 地址"
            value={draft.destination}
            onChange={(event) => update("destination", event.target.value)}
          />
        </Form.Item>
        <AdvancedOptions activeCount={advancedCount}>
          <Form.Item label="要寻找的动作">
            <Select
              aria-label="搜索动作"
              value={draft.action}
              virtual={false}
              options={[
                { value: "permit", label: "放行示例" },
                { value: "deny", label: "拒绝示例" },
                { value: "match_line", label: "指定规则行" },
              ]}
              onChange={(value) => update("action", value)}
            />
          </Form.Item>
          {draft.action === "match_line" && (
            <Form.Item label="规则行号（从0开始）">
              <Input
                aria-label="规则行号"
                value={draft.lineNumber}
                onChange={(event) => update("lineNumber", event.target.value)}
              />
            </Form.Item>
          )}
          <Form.Item label="IP 协议（可选）">
            <Select
              aria-label="搜索 IP 协议"
              mode="multiple"
              virtual={false}
              value={draft.protocols}
              options={traceProtocols.map((value) => ({
                value,
                label: value.toUpperCase(),
              }))}
              onChange={(value) => update("protocols", value)}
            />
          </Form.Item>
          <Form.Item label="源端口（可选）">
            <Input
              aria-label="搜索源端口"
              value={draft.sourcePorts}
              onChange={(event) => update("sourcePorts", event.target.value)}
            />
          </Form.Item>
          <Form.Item label="目标端口（可选）">
            <Input
              aria-label="搜索目标端口"
              value={draft.destinationPorts}
              onChange={(event) =>
                update("destinationPorts", event.target.value)
              }
            />
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
        {locked ? "重试搜索提交" : "寻找示例流量"}
      </Button>
    </Card>
  );
}
