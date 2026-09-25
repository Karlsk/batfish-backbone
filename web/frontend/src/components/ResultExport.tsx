import { useEffect, useRef, useState } from "react";
import { Button, Card, Space } from "antd";
import type { components } from "../api/schema";
import { api, unwrap } from "../api/client";
import { ErrorState } from "./States";

export function ResultExport({
  result,
}: {
  result: Pick<components["schemas"]["ResultEnvelope"], "id" | "kind">;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>();
  const flight = useRef<AbortController | null>(null);
  useEffect(() => () => flight.current?.abort(), [result.id]);
  async function download(format: "json" | "csv") {
    if (flight.current) return;
    const controller = new AbortController();
    flight.current = controller;
    setBusy(format);
    setError(undefined);
    try {
      const blob = await unwrap(
        api.GET("/api/v1/results/{result_id}/export", {
          params: { path: { result_id: result.id }, query: { format } },
          parseAs: "blob",
          signal: controller.signal,
        }),
      );
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `batfish-${result.id}.${format}`;
      document.body.append(link);
      link.click();
      link.remove();
      // Give the browser time to consume the object URL before releasing it.
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure);
    } finally {
      if (flight.current === controller) {
        flight.current = null;
        if (!controller.signal.aborted) setBusy(null);
      }
    }
  }
  return (
    <Card size="small" title="导出已保存结果">
      <Space wrap>
        <Button
          disabled={!!busy}
          aria-label="下载 JSON"
          loading={busy === "json"}
          onClick={() => void download("json")}
        >
          下载 JSON
        </Button>
        {result.kind === "table" && (
          <Button
            disabled={!!busy}
            aria-label="下载 CSV"
            loading={busy === "csv"}
            onClick={() => void download("csv")}
          >
            下载 CSV
          </Button>
        )}
      </Space>
      <p className="muted">
        包含来源快照、版本、有效参数及截断说明；导出全部已保存数据，不受当前表格筛选影响。
        {result.kind === "table"
          ? "JSON 保留原始结构；CSV 第二行为来源元数据，结构化单元格使用 JSON，公式前缀以单引号转义。"
          : "路径结果仅支持 JSON，保留 Flow、全部已保存路径及逐跳动作。"}
      </p>
      {error !== undefined && <ErrorState error={error} />}
    </Card>
  );
}
