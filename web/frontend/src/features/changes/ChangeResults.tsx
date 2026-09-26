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
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { resourceKey } from "../../app/context";
import { useSession } from "../../app/session";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import { ResultExport } from "../../components/ResultExport";
import {
  TraceSteps,
  list,
  record,
  actionLabel,
} from "../../components/TraceSteps";
import { ErrorState, EmptyState } from "../../components/States";
import { cellText } from "../results/cells";

type Comparison = Pick<
  components["schemas"]["ComparisonDTO"],
  "coverage" | "coverage_notes"
>;
type Result = components["schemas"]["ResultEnvelope"];
type DiffFile = components["schemas"]["DiffFileSummary"];
type Direction = "added" | "removed" | "changed" | "undetermined";

export function changeLabel(value: string) {
  return (
    {
      added: "候选新增",
      removed: "候选消失",
      changed: "属性变化",
      undetermined: "方向待确认",
    }[value] ?? `未知变化（${value}）`
  );
}
function ChangeTag({ value }: { value: string }) {
  const color: Record<Direction, string> = {
    added: "green",
    removed: "red",
    changed: "blue",
    undetermined: "gold",
  };
  return (
    <Tag color={color[value as Direction] ?? "default"}>
      {changeLabel(value)}
    </Tag>
  );
}
function scopeLabel(result: Result) {
  if (result.effective_parameters.operation === "reachability-diff")
    return "所选条件内未发现可达性变化；不代表全网无影响。";
  if (result.effective_parameters.operation === "routes-diff")
    return "所选路由范围内未发现模型路由变化；不代表现场转发一致。";
  return "这两份快照的原始配置文件没有文本差异；不代表网络行为等价。";
}

function ResultNotices({
  result,
  comparison,
}: {
  result: Result;
  comparison: Comparison;
}) {
  return (
    <Space orientation="vertical" style={{ width: "100%" }}>
      {comparison.coverage !== "complete" || result.coverage !== "complete" ? (
        <Alert
          type="warning"
          showIcon
          title="模型覆盖有限，变化结论仅适用于已支持的配置与所选范围。"
        />
      ) : null}
      {[...new Set([...comparison.coverage_notes, ...result.warnings])].map(
        (warning) => (
          <Alert key={warning} type="warning" showIcon title={warning} />
        ),
      )}
      {result.truncated && (
        <Alert
          type="warning"
          showIcon
          title={`证据已截断：${result.truncation_reason ?? "输出上限"}；不能据此断言完整影响范围。`}
        />
      )}
    </Space>
  );
}

function ConfigDiff({ result }: { result: Result }) {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<DiffFile | null>(null);
  const [hunkOffset, setHunkOffset] = useState(0);
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const files = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "comparison-files",
      { offset },
      result.id,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/diff/files", {
          signal,
          params: {
            path: { result_id: result.id },
            query: { offset, limit: 20 },
          },
        }),
      ),
  });
  const detail = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "comparison-file-detail",
      { fileId: selected?.file_id, hunkOffset },
      result.id,
    ),
    enabled: !!selected,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}/diff/files/{file_id}", {
          signal,
          params: {
            path: { result_id: result.id, file_id: selected!.file_id },
            query: { offset: hunkOffset, limit: 20 },
          },
        }),
      ),
  });
  return (
    <Card title="配置文件变化" extra={<span>按文件查看，详情按需读取</span>}>
      {files.isError ? (
        <ErrorState error={files.error} retry={() => void files.refetch()} />
      ) : files.data?.total === 0 ? (
        <EmptyState title={scopeLabel(result)} />
      ) : (
        <Table<DiffFile>
          rowKey="file_id"
          loading={files.isPending}
          dataSource={files.data?.items}
          pagination={{
            current: offset / 20 + 1,
            pageSize: 20,
            total: files.data?.total,
            showSizeChanger: false,
            onChange: (page) => setOffset((page - 1) * 20),
          }}
          columns={[
            {
              title: "文件",
              dataIndex: "path",
              render: (value: string) => <code>{value}</code>,
            },
            {
              title: "候选变化",
              dataIndex: "change",
              render: (value: string) => <ChangeTag value={value} />,
            },
            {
              title: "详情",
              render: (_, file) => (
                <Button
                  onClick={() => {
                    setSelected(file);
                    setHunkOffset(0);
                  }}
                >
                  查看两侧文本
                </Button>
              ),
            },
          ]}
        />
      )}
      {selected && (
        <Card
          className="change-detail"
          title={`文件详情：${selected.path}`}
          extra={<Button onClick={() => setSelected(null)}>收起详情</Button>}
        >
          <Descriptions
            size="small"
            column={2}
            items={[
              {
                key: "baseline",
                label: "基线 SHA-256",
                children: selected.baseline_sha256 ?? "无文件",
              },
              {
                key: "candidate",
                label: "候选 SHA-256",
                children: selected.candidate_sha256 ?? "无文件",
              },
            ]}
          />
          {selected.detail_truncated && (
            <Alert
              type="warning"
              title="此文件详情已截断；请查看摘要与原始文件。"
            />
          )}
          {detail.isError ? (
            <ErrorState
              error={detail.error}
              retry={() => void detail.refetch()}
            />
          ) : (
            detail.data?.hunks.map((hunk, index) => (
              <div className="change-hunk" key={`${hunkOffset}-${index}`}>
                <Tag>{hunk.tag}</Tag>
                <div className="change-sides">
                  <div>
                    <strong>基线（左）</strong>
                    <pre>
                      {hunk.baseline_lines
                        .map((line) => `${line.number}: ${line.text}`)
                        .join("\n") || "—"}
                    </pre>
                  </div>
                  <div>
                    <strong>候选（右）</strong>
                    <pre>
                      {hunk.candidate_lines
                        .map((line) => `${line.number}: ${line.text}`)
                        .join("\n") || "—"}
                    </pre>
                  </div>
                </div>
              </div>
            ))
          )}
          {(detail.data?.total ?? 0) > 20 && (
            <Space>
              <Button
                disabled={hunkOffset === 0}
                onClick={() =>
                  setHunkOffset((value) => Math.max(0, value - 20))
                }
              >
                上一页
              </Button>
              <Button
                disabled={hunkOffset + 20 >= (detail.data?.total ?? 0)}
                onClick={() => setHunkOffset((value) => value + 20)}
              >
                下一页
              </Button>
            </Space>
          )}
        </Card>
      )}
    </Card>
  );
}

function RouteDiff({ result }: { result: Result }) {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(
    null,
  );
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const rows = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "comparison-routes",
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
  return (
    <Card title="路由变化" extra="基线在左 · 候选在右">
      {rows.isError ? (
        <ErrorState error={rows.error} retry={() => void rows.refetch()} />
      ) : rows.data?.total === 0 ? (
        <EmptyState title={scopeLabel(result)} />
      ) : (
        <Table
          rowKey={(row) => JSON.stringify(row)}
          loading={rows.isPending}
          dataSource={rows.data?.rows}
          scroll={{ x: 950 }}
          pagination={{
            current: offset / 20 + 1,
            pageSize: 20,
            total: rows.data?.total,
            showSizeChanger: false,
            onChange: (page) => setOffset((page - 1) * 20),
          }}
          columns={[
            {
              title: "候选相对基线",
              dataIndex: "Change",
              render: (value: string) => <ChangeTag value={value} />,
            },
            { title: "设备", dataIndex: "Node", render: cellText },
            { title: "网段", dataIndex: "Network", render: cellText },
            {
              title: "基线下一跳",
              dataIndex: "Reference_Next_Hop",
              render: cellText,
            },
            {
              title: "候选下一跳",
              dataIndex: "Snapshot_Next_Hop",
              render: cellText,
            },
            {
              title: "详情",
              render: (_, row) => (
                <Button onClick={() => setSelected(row)}>查看完整路由</Button>
              ),
            },
          ]}
        />
      )}
      <DetailsDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title="双侧路由原始证据"
        queryKey={[result.id, "route", selected]}
        load={async () => selected}
      />
    </Card>
  );
}

function ReachabilityDiff({ result }: { result: Result }) {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(
    null,
  );
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const rows = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "comparison-reachability",
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
  return (
    <Card title="可达性变化示例" extra="同一 Flow 的基线与候选路径">
      <p className="muted">
        仅展示 SDK 在所选条件内找到的示例 Flow，数量不是全部受影响业务流。
      </p>
      {rows.isError ? (
        <ErrorState error={rows.error} retry={() => void rows.refetch()} />
      ) : rows.data?.total === 0 ? (
        <EmptyState title={scopeLabel(result)} />
      ) : (
        rows.data?.rows.map((row, index) => {
          const flow = record(row.Flow);
          const sides = [
            {
              name: "基线（左）",
              traces: list(row.Reference_Traces),
              count: Number(row.Reference_TraceCount ?? 0),
              reachable: row.Baseline_Reachable,
            },
            {
              name: "候选（右）",
              traces: list(row.Snapshot_Traces),
              count: Number(row.Snapshot_TraceCount ?? 0),
              reachable: row.Candidate_Reachable,
            },
          ];
          return (
            <Card
              key={`${result.id}-${offset + index}`}
              className="change-flow"
              title={
                <Space>
                  <ChangeTag value={String(row.Change)} />
                  <span>
                    {cellText(flow.ingressNode)} → {cellText(flow.dstIp)}
                  </span>
                </Space>
              }
              extra={
                <Button onClick={() => setSelected(row)}>原始 Flow</Button>
              }
            >
              {row.Evidence_Truncated === true && (
                <Alert
                  type="warning"
                  title="至少一侧路径证据未全部返回，方向可能待确认。"
                />
              )}
              <div className="change-sides">
                {sides.map((side) => (
                  <div key={side.name}>
                    <strong>{side.name}</strong>
                    <p>
                      {side.reachable === true
                        ? "模型可达"
                        : side.reachable === false
                          ? "模型不可达"
                          : "证据不足，无法判定"}{" "}
                      · 返回 {side.traces.length}/{side.count} 条路径
                    </p>
                    <Collapse
                      items={side.traces.map((trace, i) => ({
                        key: String(i),
                        label: `路径 ${i + 1}：${actionLabel(record(trace).disposition)}`,
                        children: (
                          <TraceSteps
                            trace={record(trace)}
                            identity={`${result.id}-${offset + index}-${side.name}-${i}`}
                            queryKey={[result.id, side.name, offset + index]}
                          />
                        ),
                      }))}
                    />
                  </div>
                ))}
              </div>
            </Card>
          );
        })
      )}
      {(rows.data?.total ?? 0) > 20 && (
        <Space>
          <Button
            disabled={offset === 0}
            onClick={() => setOffset((value) => Math.max(0, value - 20))}
          >
            上一页
          </Button>
          <Button
            disabled={offset + 20 >= (rows.data?.total ?? 0)}
            onClick={() => setOffset((value) => value + 20)}
          >
            下一页
          </Button>
        </Space>
      )}
      <DetailsDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title="Flow 与两侧路径原始证据"
        queryKey={[result.id, "flow", selected]}
        load={async () => selected}
      />
    </Card>
  );
}

export function ChangeResults({
  comparison,
  result,
}: {
  comparison: Comparison;
  result: Result;
}) {
  const operation = result.effective_parameters.operation;
  return (
    <section aria-label="比较分析结果" className="change-results">
      <Card
        className="result-summary"
        title="变化摘要"
        extra={
          <Link to={`/results/${result.id}`}>
            结果编号 {result.id.slice(0, 8)}
          </Link>
        }
      >
        <Space wrap>
          <Tag color="blue">
            {operation === "config-diff"
              ? "配置文件差异"
              : operation === "routes-diff"
                ? "路由差异"
                : "可达性差异"}
          </Tag>
          <Typography.Text>基线（左）→ 候选（右）</Typography.Text>
          <Typography.Text>
            返回{" "}
            {String(
              result.summary.returned_files ??
                result.summary.returned_rows ??
                0,
            )}{" "}
            项
          </Typography.Text>
        </Space>
        <ResultNotices comparison={comparison} result={result} />
      </Card>
      {operation === "config-diff" ? (
        <ConfigDiff key={result.id} result={result} />
      ) : operation === "routes-diff" ? (
        <RouteDiff key={result.id} result={result} />
      ) : operation === "reachability-diff" ? (
        <ReachabilityDiff key={result.id} result={result} />
      ) : (
        <EmptyState title="未知比较结果类型" />
      )}
      <ResultExport result={result} />
    </section>
  );
}
