import { expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../../api/schema";
import { prepareGraph } from "./model";
import { GraphCanvas } from "./GraphCanvas";
import { GraphResult } from "./GraphResult";
const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  selectNetwork: vi.fn(),
  selectSnapshot: vi.fn(),
  instances: [] as any[],
  factory: vi.fn(),
}));
vi.mock("cytoscape", () => ({ default: mocks.factory }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get },
}));
vi.mock("../../app/context", async (original) => ({
  ...(await original<typeof import("../../app/context")>()),
  useResourceContext: () => ({
    selectNetwork: mocks.selectNetwork,
    selectSnapshot: mocks.selectSnapshot,
  }),
}));
vi.mock("./TopologyForm", () => ({ TopologyForm: () => null }));
afterEach(() => {
  vi.clearAllMocks();
  mocks.instances.length = 0;
});
const graph = (name = "device"): components["schemas"]["GraphDTO"] => ({
  nodes: [
    { id: name, label: name, properties: {} },
    { id: "isolated", label: "孤立设备", properties: {} },
  ],
  edges: [],
  edge_type: "layer3",
  source: "layer3Edges",
  scope: {},
  truncated: false,
});
it("keeps isolated nodes and parallel edges, caps visible nodes and avoids element id collision", () => {
  const data = graph("x".repeat(220));
  data.edges = [0, 1].map((i) => ({
    id: String(i),
    source: data.nodes[0].id,
    target: "isolated",
    source_interface: "eth" + i,
    target_interface: "eth0",
    edge_type: "layer3",
    properties: {},
  }));
  data.nodes.push(
    ...Array.from({ length: 200 }, (_, i) => ({
      id: String(i),
      label: String(i),
      properties: {},
    })),
  );
  const result = prepareGraph(data);
  expect(result.nodes).toHaveLength(200);
  expect(result.edges).toHaveLength(2);
  expect(result.truncated).toBe(true);
  expect(new Set(result.elements.map((e) => e.data.id)).size).toBe(
    result.elements.length,
  );
  expect(result.elements[0].data.label).toBe("x".repeat(220));
});
it("destroys the graph and resize observer on data replacement and unmount", () => {
  mocks.factory.mockImplementation(() => {
    const instance = {
      on: vi.fn(),
      destroy: vi.fn(),
      resize: vi.fn(),
      fit: vi.fn(),
      style: vi.fn(),
    };
    mocks.instances.push(instance);
    return instance;
  });
  const view = render(
    <ConfigProvider>
      <GraphCanvas graph={graph()} onSelect={() => {}} />
    </ConfigProvider>,
  );
  expect(mocks.instances).toHaveLength(1);
  view.rerender(
    <ConfigProvider>
      <GraphCanvas graph={graph("new")} onSelect={() => {}} />
    </ConfigProvider>,
  );
  expect(mocks.instances[0].destroy).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(mocks.instances[1].destroy).toHaveBeenCalledTimes(1);
});
it("does not render a late graph from the previous snapshot/result", async () => {
  mocks.factory.mockImplementation(() => ({
    on: vi.fn(),
    destroy: vi.fn(),
    resize: vi.fn(),
    fit: vi.fn(),
    style: vi.fn(),
  }));
  let oldResolve: (data: unknown) => void = () => {};
  mocks.get.mockImplementation(async (_path, options) => {
    const id = options.params.path.result_id;
    if (id === "old")
      return await new Promise((resolve) => {
        oldResolve = resolve;
      });
    return { data: graph("current"), response: new Response("{}") };
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const element = (id: string) => (
    <ConfigProvider>
      <MemoryRouter>
        <QueryClientProvider client={client}>
          <GraphResult
            key={id}
            result={
              {
                id,
                context: { network_id: "network", snapshot_id: id },
              } as components["schemas"]["ResultEnvelope"]
            }
          />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>
  );
  const view = render(element("old"));
  await waitFor(() => expect(mocks.get).toHaveBeenCalled());
  view.rerender(element("new"));
  await screen.findByRole(
    "button",
    { name: "设备详情 current" },
    { timeout: 5000 },
  );
  await act(async () =>
    oldResolve({ data: graph("stale"), response: new Response("{}") }),
  );
  expect(screen.queryByRole("button", { name: "设备详情 stale" })).toBeNull();
});

it("one-hop action resets a wider neighborhood instead of keeping its previous radius", async () => {
  const { default: userEvent } = await import("@testing-library/user-event");
  mocks.factory.mockImplementation(() => ({
    on: vi.fn(),
    destroy: vi.fn(),
    resize: vi.fn(),
    fit: vi.fn(),
  }));
  mocks.get.mockImplementation(async () => ({
    data: graph("current"),
    response: new Response("{}"),
  }));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <ConfigProvider>
      <MemoryRouter>
        <QueryClientProvider client={client}>
          <GraphResult
            result={
              {
                id: "r",
                context: { network_id: "n", snapshot_id: "s" },
              } as components["schemas"]["ResultEnvelope"]
            }
          />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
  await screen.findByRole("button", { name: "聚焦 current" });
  await userEvent.click(screen.getByRole("combobox", { name: "邻居跳数" }));
  await userEvent.click(screen.getByRole("option", { name: "2 跳邻居" }));
  await screen.findByText(/current 的 2 跳邻域/);
  await userEvent.click(screen.getByRole("button", { name: "聚焦 isolated" }));
  await screen.findByText(/isolated 的 1 跳邻域/);
});

for (const cancel of ["unmount", "result change"])
  it(`ignores route lookups after ${cancel}`, async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    mocks.factory.mockImplementation(() => ({
      on: vi.fn(),
      destroy: vi.fn(),
      resize: vi.fn(),
      fit: vi.fn(),
    }));
    mocks.selectNetwork.mockResolvedValue(true);
    mocks.selectSnapshot.mockResolvedValue(true);
    const pending: Array<(value: unknown) => void> = [];
    mocks.get.mockImplementation(async (path) => {
      if (path.includes("/graph"))
        return { data: graph("current"), response: new Response("{}") };
      return new Promise((resolve) => pending.push(resolve));
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const element = (id: string) => (
      <ConfigProvider>
        <MemoryRouter>
          <QueryClientProvider client={client}>
            <GraphResult
              result={
                {
                  id,
                  context: { network_id: "n", snapshot_id: id },
                } as components["schemas"]["ResultEnvelope"]
              }
            />
          </QueryClientProvider>
        </MemoryRouter>
      </ConfigProvider>
    );
    const view = render(element("old"));
    await userEvent.click(
      await screen.findByRole("button", { name: "设备详情 current" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "查询该设备路由" }),
    );
    await waitFor(() => expect(pending).toHaveLength(2));
    if (cancel === "unmount") view.unmount();
    else view.rerender(element("new"));
    await act(async () => {
      for (const resolve of pending)
        resolve({
          data: { id: "old", display_name: "old" },
          response: new Response("{}"),
        });
    });
    expect(mocks.selectNetwork).not.toHaveBeenCalled();
    expect(mocks.selectSnapshot).not.toHaveBeenCalled();
  });
