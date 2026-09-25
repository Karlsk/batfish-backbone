import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Table,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { resourceKey } from "../../app/context";
import { useSession } from "../../app/session";
import { ErrorState, EmptyState, LoadingState } from "../../components/States";
import { DetailsDrawer } from "../../components/DetailsDrawer";
import { ResultSummary } from "../../components/ResultSummary";
import { cellText, columnLabels, primaryColumns } from "./cells";
export function ResultsPage() {
  const { resultId } = useParams();
  return <ResultView key={resultId} resultId={resultId!} />;
}
function ResultView({ resultId }: { resultId: string }) {
  const session = useSession();
  const [details, setDetails] = useState(false);
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: null, snapshotId: null },
      "result",
      {},
      resultId,
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/results/{result_id}", {
          signal,
          params: { path: { result_id: resultId } },
        }),
      ),
  });
  if (query.isPending) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} />;
  const result = query.data;
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>分析结果</Typography.Title>
          <span className="record-id">结果编号：{result.id}</span>
        </div>
        <Button onClick={() => setDetails(true)}>有效参数与来源</Button>
      </div>
      <ResultSummary result={result} />
      <p className="muted">
        此结果固定来自上述快照；切换顶部上下文仅影响后续查询。
      </p>
      {result.kind === "table" ? (
        <ResultTable result={result} />
      ) : (
        <EmptyState title="此结果请通过对应分析视图查看" />
      )}
      <DetailsDrawer
        open={details}
        onClose={() => setDetails(false)}
        title="结果参数与来源"
        queryKey={resourceKey(
          session?.user_id ?? null,
          {
            networkId: result.context.network_id,
            snapshotId: result.context.snapshot_id,
          },
          "result-details",
          {},
          result.id,
        )}
        load={async () => ({
          context: result.context,
          effective_parameters: result.effective_parameters,
          schema_version: result.schema_version,
        })}
      />
    </>
  );
}
export function ResultTable({
  result,
}: {
  result: components["schemas"]["ResultEnvelope"];
}) {
  const session = useSession();
  const [offset, setOffset] = useState(0);
  const [column, setColumn] = useState<string>();
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState<{
    column: string;
    value: string;
  } | null>(null);
  const [row, setRow] = useState<Record<string, unknown> | null>(null);
  const [allColumns, setAllColumns] = useState(false);
  const params = {
    offset,
    limit: 20,
    ...(filter
      ? { filters: JSON.stringify([{ ...filter, op: "contains" }]) }
      : {}),
  };
  const context = {
    networkId: result.context.network_id,
    snapshotId: result.context.snapshot_id,
  };
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      context,
      "rows",
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
  const keys = query.data?.columns.map((c) => c.key) ?? [];
  const selected = allColumns ? keys : primaryColumns(keys);
  return (
    <Card title="结果证据">
      <Space wrap className="filter-bar">
        <Select
          aria-label="结果筛选列"
          placeholder="选择筛选列"
          style={{ width: 180 }}
          virtual={false}
          value={column}
          options={(
            query.data?.columns
              .filter((c) => ["String", "Ip", "Prefix"].includes(c.type))
              .map((c) => c.key) ?? []
          ).map((value) => ({
            value,
            label: columnLabels[value] ?? value,
          }))}
          onChange={setColumn}
        />
        <Input
          aria-label="结果筛选值"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="仅筛选文本列"
          style={{ width: 200 }}
        />
        <Button
          onClick={() => {
            setOffset(0);
            setFilter(column && input ? { column, value: input } : null);
          }}
        >
          应用筛选
        </Button>
        <Button
          onClick={() => {
            setOffset(0);
            setInput("");
            setFilter(null);
          }}
        >
          清除筛选
        </Button>
        <Button onClick={() => setAllColumns((v) => !v)}>
          {allColumns ? "仅关键列" : "显示全部列"}
        </Button>
      </Space>
      {filter && (
        <p>
          生效筛选：{columnLabels[filter.column] ?? filter.column} 包含「
          {filter.value}」
        </p>
      )}
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <Table
          rowKey="_key"
          loading={query.isPending}
          dataSource={query.data?.rows.map((value, index) => ({
            ...value,
            _key: `${result.id}:${offset + index}`,
          }))}
          scroll={{ x: Math.max(800, selected.length * 180) }}
          locale={{
            emptyText: query.isPending
              ? "正在读取结果"
              : "没有匹配结果；这是有效的空结果，并非任务失败。",
          }}
          pagination={{
            current: offset / 20 + 1,
            pageSize: 20,
            total: query.data?.total,
            showSizeChanger: false,
            onChange: (p) => setOffset((p - 1) * 20),
          }}
          columns={[
            ...selected.map((key, index) => ({
              title: columnLabels[key] ?? key,
              dataIndex: key,
              key,
              width: key.includes("Next_Hop") ? 240 : 180,
              fixed: index === 0 ? ("left" as const) : undefined,
              render: (value: unknown) => (
                <span className="result-cell" title={cellText(value)}>
                  {cellText(value)}
                </span>
              ),
            })),
            {
              title: "详情",
              key: "details",
              fixed: "right",
              width: 90,
              render: (_, value) => (
                <Button
                  type="link"
                  onClick={() => {
                    const { _key, ...raw } = value;
                    setRow(raw);
                  }}
                >
                  原始行
                </Button>
              ),
            },
          ]}
        />
      )}
      <DetailsDrawer
        open={!!row}
        title="原始结果行"
        onClose={() => setRow(null)}
        queryKey={resourceKey(
          session?.user_id ?? null,
          context,
          "raw-row",
          { row },
          result.id,
        )}
        load={async () => row}
      />
    </Card>
  );
}
