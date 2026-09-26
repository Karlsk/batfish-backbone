import { afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../../api/schema";
import { BgpResult } from "./BgpResult";
import { BgpForm } from "./BgpForm";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  selectNetwork: vi.fn(),
  selectSnapshot: vi.fn(),
}));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get, POST: mocks.post },
}));
vi.mock("../../app/context", async (original) => ({
  ...(await original<typeof import("../../app/context")>()),
  useResourceContext: () => ({
    selectNetwork: mocks.selectNetwork,
    selectSnapshot: mocks.selectSnapshot,
  }),
}));
vi.mock("../inventory/useCandidates", () => ({
  useCandidates: () => ({ nodes: [], controls: null }),
}));
vi.mock("../../components/useDraftGuard", () => ({
  useDraftGuard: () => ({ holder: null, allowNavigation: () => {} }),
}));
afterEach(() => vi.clearAllMocks());
const result = (mode: "status" | "compatibility") =>
  ({
    id: mode,
    kind: "table",
    context: { network_id: "network", snapshot_id: "snapshot" },
    effective_parameters: {
      operation: "bgp-sessions",
      request: { options: { mode } },
    },
  }) as unknown as components["schemas"]["ResultEnvelope"];
function shell(node: React.ReactNode) {
  return render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          {node}
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
}
it("keeps status and compatibility analyses distinct, including default minimal request", async () => {
  mocks.post.mockResolvedValue({
    data: { id: "job" },
    response: new Response("{}"),
  });
  shell(<BgpForm networkId="network" snapshotId="snapshot" />);
  await userEvent.click(screen.getByRole("button", { name: "分析 BGP 会话" }));
  await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
  expect(mocks.post.mock.calls[0][1].body.options.mode).toBe("status");
  expect(mocks.post.mock.calls[0][0]).toContain("/analyses/bgp-sessions");
});
it("shows a one-ended session and unknown remote without invented route target", async () => {
  mocks.get.mockResolvedValue({
    data: {
      columns: [
        "Node",
        "Remote_Node",
        "Established_Status",
        "Local_Interface",
        "Local_AS",
        "Address_Families",
      ].map((key) => ({ key, label: key, type: "String" })),
      rows: [
        {
          Node: { name: "c1" },
          Remote_Node: null,
          Established_Status: "NOT_COMPATIBLE",
          Local_Interface: { name: "Ethernet0" },
          Local_AS: 65001,
          Address_Families: ["IPV4_UNICAST"],
        },
      ],
      offset: 0,
      limit: 20,
      total: 1,
      truncated: false,
    },
    response: new Response("{}"),
  });
  shell(<BgpResult result={result("status")} />);
  expect(await screen.findByText("NOT_COMPATIBLE")).toBeTruthy();
  expect(screen.getByText("远端未知")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "查询远端设备路由" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "查看会话详情" }));
  expect(await screen.findByText(/65001 \/ —/)).toBeTruthy();
  expect(screen.getByText("IPV4_UNICAST")).toBeTruthy();
  expect(screen.getByText(/模型计算，非实时设备状态/)).toBeTruthy();
});
it("filters raw status on the server and labels compatibility results separately", async () => {
  mocks.get.mockImplementation(async (_path, args) => ({
    data: {
      columns: [
        {
          key: "Configured_Status",
          label: "Configured_Status",
          type: "String",
        },
      ],
      rows: [
        {
          Configured_Status: args.params.query.filters
            ? "NO_MATCH"
            : "UNIQUE_MATCH",
        },
      ],
      offset: 0,
      limit: 20,
      total: 1,
      truncated: false,
    },
    response: new Response("{}"),
  }));
  shell(<BgpResult result={result("compatibility")} />);
  expect(await screen.findByText("UNIQUE_MATCH")).toBeTruthy();
  await userEvent.type(
    screen.getByRole("textbox", { name: "原始状态筛选" }),
    "NO_MATCH",
  );
  await userEvent.click(screen.getByRole("button", { name: "应用状态筛选" }));
  await screen.findByText("NO_MATCH");
  expect(JSON.parse(mocks.get.mock.lastCall![1].params.query.filters)).toEqual([
    { column: "Configured_Status", op: "eq", value: "NO_MATCH" },
  ]);
  expect(screen.getByText(/兼容性分析/)).toBeTruthy();
});
