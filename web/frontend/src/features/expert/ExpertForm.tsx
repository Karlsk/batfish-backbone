import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  Select,
  Typography,
} from "antd";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { components } from "../../api/schema";
import { api, ApiError, unwrap } from "../../api/client";
import { useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { EmptyState, ErrorState } from "../../components/States";
import { useDraftGuard } from "../../components/useDraftGuard";
import {
  buildExpertParameters,
  defaultExpertDraft,
  effectiveExpertParameters,
  schemaFields,
  type ExpertDraft,
} from "./model";

type Capability = components["schemas"]["Capability"];
type Request = components["schemas"]["ExpertQueryRequest"];

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function ExpertPage() {
  const { network, snapshot } = useResourceContext();
  return (
    <>
      <Typography.Title level={2}>专家查询</Typography.Title>
      {network && snapshot ? (
        <ExpertForm
          key={`${network.id}:${snapshot.id}`}
          networkId={network.id}
          snapshotId={snapshot.id}
        />
      ) : (
        <EmptyState
          title="请先选择网络与就绪快照"
          action={
            <Link to="/snapshots">
              <Button>选择快照</Button>
            </Link>
          }
        />
      )}
    </>
  );
}

export function ExpertForm({
  networkId,
  snapshotId,
}: {
  networkId: string;
  snapshotId: string;
}) {
  const session = useSession();
  const navigate = useNavigate();
  const catalog = useQuery({
    queryKey: ["capabilities", session?.user_id ?? null],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/capabilities", { signal })),
  });
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState<ExpertDraft>({
    fields: {},
    optionsText: "{}",
  });
  const [validation, setValidation] = useState("");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const flight = useRef(false);
  const alive = useRef(true);
  const attempt = useRef<{ key: string; body: Request } | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const capability = catalog.data?.find((item) => item.id === selected);
  const guard = useDraftGuard(locked || !!selected, busy);
  function choose(id: string) {
    const next = catalog.data?.find((item) => item.id === id);
    if (!next || !next.enabled || locked) return;
    setSelected(id);
    setDraft(defaultExpertDraft(next));
    setValidation("");
    setError(undefined);
    attempt.current = null;
  }
  function updateField(name: string, value: string) {
    setValidation("");
    setError(undefined);
    setDraft((previous) => ({
      ...previous,
      fields: { ...previous.fields, [name]: value },
    }));
  }
  let preview = "选择能力后查看有效参数。";
  let activeCount = 0;
  if (capability) {
    try {
      const requested = buildExpertParameters(capability, draft);
      const parameters = effectiveExpertParameters(capability, draft);
      preview = JSON.stringify(parameters, null, 2);
      const defaults = object(capability.defaults.options);
      activeCount = Object.entries(object(requested.options)).filter(
        ([key, value]) =>
          JSON.stringify(value) !== JSON.stringify(defaults[key]),
      ).length;
    } catch {
      preview = "参数尚未完整或 JSON 格式有误；输入会保留。";
    }
  }
  async function submit() {
    if (flight.current || !capability?.enabled) return;
    setValidation("");
    let parameters: Request["parameters"];
    try {
      parameters = buildExpertParameters(capability, draft);
    } catch (caught) {
      setValidation((caught as Error).message);
      return;
    }
    attempt.current ??= {
      key: crypto.randomUUID(),
      body: { question_id: capability.id, parameters },
    };
    flight.current = true;
    setBusy(true);
    setLocked(true);
    setError(undefined);
    try {
      const job = await unwrap(
        api.POST(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/query",
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
    <Card title="已登记能力查询">
      {guard.holder}
      <Alert
        type="info"
        title="这里只能运行目录中已开放的能力；结果仍基于当前快照配置模型。"
      />
      {catalog.isError && (
        <ErrorState
          error={catalog.error}
          retry={() => void catalog.refetch()}
        />
      )}
      {error != null && <ErrorState error={error} />}
      {error instanceof ApiError && error.fieldErrors.length > 0 && (
        <Alert
          type="warning"
          title="需要修正的字段"
          description={error.fieldErrors
            .map((item) => `${item.path.join(".")}: ${item.message}`)
            .join("；")}
        />
      )}
      {validation && <Alert type="error" title={validation} />}
      {locked && !busy && error != null && (
        <Alert type="info" title="提交状态未知；重试保留原参数和请求标识。" />
      )}
      <Form layout="vertical" disabled={busy || locked}>
        <Form.Item label="已开放能力">
          <Select
            aria-label="专家能力"
            value={selected || undefined}
            virtual={false}
            loading={catalog.isPending}
            options={(catalog.data ?? []).map((item) => ({
              value: item.id,
              label: `${item.label} · ${item.id}`,
              disabled: !item.enabled,
              title: item.disabled_reason ?? undefined,
            }))}
            onChange={choose}
            placeholder="选择目录中的已开放问题"
          />
        </Form.Item>
        {capability && (
          <>
            <p className="muted">
              {capability.result_kind} 结果 ·
              {capability.requires_dataplane ? "需要数据面计算" : "配置查询"} ·
              schema v{capability.schema_version}
            </p>
            {schemaFields(capability).map(([name, rawSchema]) => {
              const schema = object(rawSchema);
              const title =
                typeof schema.title === "string" ? schema.title : name;
              const isString = schema.type === "string";
              const choices = Array.isArray(schema.enum)
                ? schema.enum.filter(
                    (value): value is string => typeof value === "string",
                  )
                : [];
              return (
                <Form.Item
                  key={name}
                  label={`${title} (${name})`}
                  required={capability.required_fields.includes(name)}
                >
                  {choices.length ? (
                    <Select
                      aria-label={title}
                      value={draft.fields[name] || undefined}
                      options={choices.map((value) => ({
                        value,
                        label: value,
                      }))}
                      onChange={(value) => updateField(name, value)}
                    />
                  ) : isString ? (
                    <Input
                      aria-label={title}
                      value={draft.fields[name] ?? ""}
                      onChange={(event) =>
                        updateField(name, event.target.value)
                      }
                    />
                  ) : (
                    <Input.TextArea
                      aria-label={title}
                      rows={2}
                      value={draft.fields[name] ?? ""}
                      onChange={(event) =>
                        updateField(name, event.target.value)
                      }
                      placeholder="按 JSON Schema 输入结构化值；留空使用默认"
                    />
                  )}
                </Form.Item>
              );
            })}
            <p className="muted">
              预计有效参数（含默认值，提交时由服务端复核）
            </p>
            <pre className="raw-detail">{preview}</pre>
            <AdvancedOptions activeCount={activeCount}>
              <Form.Item label="options JSON">
                <Input.TextArea
                  aria-label="专家 options JSON"
                  rows={8}
                  value={draft.optionsText}
                  onChange={(event) => {
                    setValidation("");
                    setError(undefined);
                    setDraft((previous) => ({
                      ...previous,
                      optionsText: event.target.value,
                    }));
                  }}
                />
              </Form.Item>
              <Collapse
                items={[
                  {
                    key: "schema",
                    label: "查看此能力的参数 JSON Schema",
                    children: (
                      <pre className="raw-detail">
                        {JSON.stringify(capability.parameters_schema, null, 2)}
                      </pre>
                    ),
                  },
                ]}
              />
            </AdvancedOptions>
          </>
        )}
      </Form>
      <Button
        className="action-bar"
        type="primary"
        loading={busy}
        disabled={!capability?.enabled}
        onClick={() => void submit()}
      >
        {locked ? "重试专家查询提交" : "运行专家查询"}
      </Button>
    </Card>
  );
}
