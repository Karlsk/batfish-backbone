import { useState } from "react";
import { Alert, Button, Drawer, Space } from "antd";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../../api/client";
import { resourceKey } from "../../../app/context";
import { useSession } from "../../../app/session";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../../../components/States";
import type { components } from "../../../api/schema";
export type SourceTarget = {
  fileId: string;
  path: string;
  lines: number[];
  offset: number;
};
export function sourceTarget(
  location: components["schemas"]["SourceLocation"],
): SourceTarget | null {
  if (!location.file_id) return null;
  const lines = [
    ...new Set(location.lines.filter((n) => Number.isSafeInteger(n) && n > 0)),
  ].sort((a, b) => a - b);
  return {
    fileId: location.file_id,
    path: location.path,
    lines,
    offset: Math.max(0, (lines[0] ?? 1) - 6),
  };
}
export function SourceLines({
  lines,
  highlights,
}: {
  lines: components["schemas"]["SourceLine"][];
  highlights: number[];
}) {
  return (
    <pre className="source-code">
      {lines.map((line) => (
        <div
          className="source-line"
          key={line.number}
          data-line={line.number}
          data-highlight={String(highlights.includes(line.number))}
        >
          <span className="line-number">{line.number}</span>
          <code>
            {line.text}
            {line.truncated ? " …（此行已截断）" : ""}
          </code>
        </div>
      ))}
    </pre>
  );
}
export function SourceDrawer({
  networkId,
  snapshotId,
  target,
  onClose,
}: {
  networkId: string;
  snapshotId: string;
  target: SourceTarget | null;
  onClose: () => void;
}) {
  return target ? (
    <SourceView
      key={`${networkId}:${snapshotId}:${target.fileId}:${target.lines.join(",")}`}
      networkId={networkId}
      snapshotId={snapshotId}
      target={target}
      onClose={onClose}
    />
  ) : null;
}
function SourceView({
  networkId,
  snapshotId,
  target,
  onClose,
}: {
  networkId: string;
  snapshotId: string;
  target: SourceTarget;
  onClose: () => void;
}) {
  const session = useSession();
  const [offset, setOffset] = useState(target.offset);
  const query = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId },
      "source-lines",
      { fileId: target.fileId, offset, limit: 50 },
    ),
    queryFn: ({ signal }) =>
      unwrap(
        api.GET(
          "/api/v1/networks/{network_id}/snapshots/{snapshot_id}/files/{file_id}",
          {
            signal,
            params: {
              path: {
                network_id: networkId,
                snapshot_id: snapshotId,
                file_id: target.fileId,
              },
              query: { offset, limit: 50 },
            },
          },
        ),
      ),
    retry: false,
  });
  const page = query.data;
  return (
    <Drawer
      open
      title={`配置文件 · ${target.path}`}
      onClose={onClose}
      size={760}
    >
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        page && (
          <>
            <p className="record-id">
              快照：{snapshotId} · 编码：{page.encoding}
            </p>
            {!target.lines.length && (
              <Alert
                type="info"
                title="诊断未提供行号，仅展示原始文件，不高亮推测位置。"
              />
            )}
            {target.lines.length > 0 &&
              !page.lines.some((line) =>
                target.lines.includes(line.number),
              ) && (
                <Alert
                  type="info"
                  title="指定行未在本页返回，未生成替代高亮。"
                />
              )}
            {page.warnings.map((w) => (
              <Alert key={w} type="warning" showIcon title={w} />
            ))}
            {page.lines.length ? (
              <SourceLines lines={page.lines} highlights={target.lines} />
            ) : (
              <EmptyState title="当前页没有可显示的文本行" />
            )}
            <Space>
              <Button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 50))}
              >
                上一页
              </Button>
              <span>
                从第 {offset + 1} 行开始
                {page.total !== null ? ` / 共 ${page.total} 行` : ""}
              </span>
              <Button
                disabled={
                  page.total !== null
                    ? offset + 50 >= page.total
                    : page.lines.length < 50
                }
                onClick={() => setOffset(offset + 50)}
              >
                下一页
              </Button>
            </Space>
          </>
        )
      )}
    </Drawer>
  );
}
