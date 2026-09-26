import { afterEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../../api/schema";
import {
  FilterSearchResult,
  RuleReachabilityResult,
  reachabilityReason,
} from "./AdvancedResults";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get },
}));
vi.mock("../../app/context", async (original) => ({
  ...(await original<typeof import("../../app/context")>()),
  useResourceContext: () => ({
    selectNetwork: vi.fn().mockResolvedValue(true),
    selectSnapshot: vi.fn().mockResolvedValue(true),
  }),
}));
afterEach(() => vi.clearAllMocks());

const base = {
  id: "result",
  kind: "table",
  context: { network_id: "network", snapshot_id: "snapshot" },
  warnings: [],
  truncated: false,
  quality_summary: {},
} as unknown as components["schemas"]["ResultEnvelope"];

function show(
  element: React.ReactNode,
  rows: Record<string, unknown>[],
  truncated = false,
) {
  mocks.get.mockResolvedValue({
    data: { rows, total: rows.length, offset: 0, limit: 20, truncated },
    response: new Response("{}"),
  });
  return render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          {element}
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
}

it("keeps a no-witness search scoped and unknown", async () => {
  const result = {
    ...base,
    effective_parameters: {
      operation: "search-filters",
      request: {
        nodes: { mode: "literal", values: ["c2"] },
        filters: { mode: "literal", values: ["WEB-SEARCH"] },
        action: "permit",
        options: {
          headers: { source_ip: "192.0.2.1", destination_ip: "198.51.100.1" },
        },
      },
    },
  } as components["schemas"]["ResultEnvelope"];
  show(<FilterSearchResult result={result} />, []);
  expect(await screen.findByText(/当前条件未找到示例流量/)).toBeTruthy();
  expect(screen.getByText(/192\.0\.2\.1/)).toBeTruthy();
  expect(screen.queryByText("策略安全")).toBeNull();
});

it("keeps blocking and independently unmatchable rules distinct with raw evidence", async () => {
  const result = {
    ...base,
    effective_parameters: {
      operation: "filter-line-reachability",
      request: {
        nodes: { mode: "literal", values: ["c2"] },
        filters: { mode: "literal", values: ["WEB-SEARCH"] },
        options: { ignore_composites: true },
      },
    },
  } as components["schemas"]["ResultEnvelope"];
  show(<RuleReachabilityResult result={result} />, [
    {
      Unreachable_Line: "permit ip host 10.64.0.1 host 10.64.0.4",
      Reason: "BLOCKING_LINES",
      Blocking_Lines: ["deny ip any any"],
      Sources: [{ filename: "configs/c2.cfg", lines: [37] }],
    },
    {
      Unreachable_Line: "permit ip object-group EMPTY-GROUP any",
      Reason: "INDEPENDENTLY_UNMATCHABLE",
      Blocking_Lines: [],
      Sources: null,
      Additional_Info: null,
    },
  ]);
  expect((await screen.findAllByText("被前序规则阻挡")).length).toBeGreaterThan(
    0,
  );
  expect(screen.getByText("匹配条件本身为空")).toBeTruthy();
  expect(reachabilityReason({ Reason: "UNKNOWN" }).kind).toBe("unknown");
  await userEvent.click(screen.getAllByRole("button", { name: "查看证据" })[1]);
  const drawer = screen.getByRole("dialog", { name: "规则诊断详情" });
  expect(within(drawer).getByText(/没有阻挡规则证据/)).toBeTruthy();
  await userEvent.click(within(drawer).getByText("原始 SDK 证据"));
  expect(within(drawer).getByText(/INDEPENDENTLY_UNMATCHABLE/)).toBeTruthy();
});
