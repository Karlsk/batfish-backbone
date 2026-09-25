import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DetailsDrawer } from "./DetailsDrawer";
import { ResultSummary } from "./ResultSummary";
import type { components } from "../api/schema";
it("loads details only when opened", async () => {
  const load = vi.fn(async () => ({ evidence: "已加载证据" }));
  const client = new QueryClient();
  const element = (open: boolean) => (
    <QueryClientProvider client={client}>
      <DetailsDrawer
        open={open}
        title="结果详情"
        onClose={() => {}}
        queryKey={["resource", "u", "n", "s", "r", "details"]}
        load={load}
      />
    </QueryClientProvider>
  );
  const view = render(element(false));
  expect(load).not.toHaveBeenCalled();
  view.rerender(element(true));
  await screen.findByText(/已加载证据/);
  expect(load).toHaveBeenCalledTimes(1);
});
it("keeps limitations and truncation visible at summary level", () => {
  const result = {
    id: "r",
    kind: "traces",
    schema_version: "1",
    context: {
      network_id: "n",
      snapshot_id: "s",
      engine_network: "engine-n",
      engine_snapshot: "engine-s",
      engine_version: "0.36.0",
      sdk_version: "2026.9.17.3748",
      schema_version: "1",
    },
    effective_parameters: {},
    summary: { returned_rows: 2, ignore_filters: true },
    warnings: ["虚拟推演不代表真实探测"],
    coverage: "limited",
    truncated: true,
    truncation_reason: "最大路径数",
    created_at: "2026-09-25T00:00:00Z",
  } as components["schemas"]["ResultEnvelope"];
  render(<ResultSummary result={result} />);
  expect(screen.getByText(/模型覆盖有限/)).toBeTruthy();
  expect(screen.getByText(/结果已截断/)).toBeTruthy();
  expect(screen.getByText(/忽略了 ACL/)).toBeTruthy();
});
