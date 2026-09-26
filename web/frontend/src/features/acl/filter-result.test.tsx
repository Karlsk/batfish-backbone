import { afterEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../../api/schema";
import { FilterResult } from "./FilterResult";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get },
}));
vi.mock("../../app/context", async (original) => ({
  ...(await original<typeof import("../../app/context")>()),
  useResourceContext: () => ({
    selectNetwork: vi.fn(),
    selectSnapshot: vi.fn(),
  }),
}));
afterEach(() => vi.clearAllMocks());

const result = {
  id: "result",
  kind: "table",
  context: { network_id: "network", snapshot_id: "snapshot" },
  effective_parameters: { operation: "test-filters" },
} as unknown as components["schemas"]["ResultEnvelope"];

function show(rows: Record<string, unknown>[]) {
  mocks.get.mockResolvedValue({
    data: { rows, total: rows.length, offset: 0, limit: 20, truncated: false },
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
          <FilterResult result={result} />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
}

it("shows no matching ACL as unknown, never as a permit", async () => {
  show([]);
  expect(await screen.findByText("没有匹配的 ACL，无法判断")).toBeTruthy();
  expect(screen.queryByText("ACL 局部放行")).toBeNull();
});

it("shows implicit deny without inventing a rule number or source line", async () => {
  show([
    {
      Node: { name: "c2" },
      Filter_Name: "WEB-TEST",
      Action: "DENY",
      Implicit_Deny: true,
      Line_Content: "no-match",
      Source_References: [],
      Flow: { srcIp: "10.64.0.1" },
      Trace: [],
    },
  ]);
  expect((await screen.findAllByText("隐式拒绝")).length).toBeGreaterThan(0);
  expect(screen.getByText("没有匹配规则（隐式拒绝）")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "查看证据" }));
  expect(await screen.findByText("没有可用来源引用")).toBeTruthy();
  expect(screen.queryByText(/规则行号/)).toBeNull();
});
