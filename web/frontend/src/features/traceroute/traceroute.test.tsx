import { it, expect } from "vitest";
import {
  buildTrace,
  defaultTrace,
  literalLocation,
  traceFromAcl,
} from "./requests";
it("validates destination, protocol ports and max traces before submitting", () => {
  const draft = { ...defaultTrace(), node: "r1", destination: "10.0.0.2" };
  expect(buildTrace(draft).destination_ip).toBe("10.0.0.2");
  expect(() => buildTrace({ ...draft, destination: "::1" })).toThrow();
  expect(() => buildTrace({ ...draft, ports: "443" })).toThrow();
  expect(() => buildTrace({ ...draft, maxTraces: 21 })).toThrow();
  expect(
    buildTrace({
      ...draft,
      protocols: ["tcp"],
      ports: "443",
      ignoreFilters: true,
    }),
  ).toMatchObject({
    options: { destination_ports: [443], ignore_filters: true },
  });
});

it("prefills ACL flow only for the same snapshot and still requires a start device", () => {
  const preset = {
    networkId: "network",
    snapshotId: "snapshot",
    source: "10.64.0.1",
    destination: "10.64.0.2",
    options: {
      ip_protocols: ["tcp"],
      source_ports: [12345],
      destination_ports: [443],
    },
  };
  const draft = traceFromAcl(preset, "network", "snapshot");
  expect(draft).toMatchObject({
    node: "",
    source: "10.64.0.1",
    destination: "10.64.0.2",
    protocols: ["tcp"],
    sourcePorts: "12345",
    ports: "443",
  });
  expect(() => buildTrace(draft)).toThrow("起点设备");
  expect(traceFromAcl(preset, "other", "snapshot")).toEqual(defaultTrace());
});
it("keeps literal node/interface distinct from expert location", () => {
  expect(literalLocation("a.*", "Eth0")).toContain("\\x{2a}");
  expect(
    buildTrace({
      ...defaultTrace(),
      mode: "expression",
      expression: "c1,c2",
      destination: "10.64.0.4",
    }).start_location,
  ).toBe("c1,c2");
});

import { vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TraceResults } from "./TraceResults";
import type { components } from "../../api/schema";
const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get },
}));
afterEach(() => vi.clearAllMocks());
it("allows every flow and path, retains mixed dispositions, truncation and unknown actions", async () => {
  const flows = [
    {
      flow_id: "0",
      headers: { srcIp: "1.1.1.1", dstIp: "2.2.2.2", ipProtocol: "ICMP" },
      start_location: "r1",
      trace_count: 3,
      returned_trace_count: 2,
      dispositions: { ACCEPTED: 1, DENIED_IN: 1 },
      truncated: true,
    },
    {
      flow_id: "1",
      headers: { srcIp: "3.3.3.3", dstIp: "4.4.4.4", ipProtocol: "UDP" },
      start_location: "r2",
      trace_count: 1,
      returned_trace_count: 1,
      dispositions: { NO_ROUTE: 1 },
      truncated: false,
    },
  ];
  mocks.get.mockImplementation(async (path, options) => ({
    data: path.endsWith("/flows")
      ? { items: flows, total: 2, offset: 0, limit: 5, truncated: true }
      : {
          items:
            options.params.path.flow_id === "0"
              ? [
                  {
                    disposition: "ACCEPTED",
                    hops: [
                      {
                        node: { name: "first-node" },
                        steps: [{ action: "ACCEPTED", detail: {} }],
                      },
                    ],
                  },
                  {
                    disposition: "DENIED_IN",
                    hops: [
                      {
                        node: { name: "acl-node" },
                        steps: [
                          {
                            action: "FUTURE_ACTION",
                            detail: { evidence: "preserved" },
                          },
                        ],
                      },
                    ],
                  },
                ]
              : [
                  {
                    disposition: "NO_ROUTE",
                    hops: [
                      {
                        node: { name: "second-flow-node" },
                        steps: [{ action: "NO_ROUTE", detail: {} }],
                      },
                    ],
                  },
                ],
          total: options.params.path.flow_id === "0" ? 2 : 1,
          trace_count: 3,
          offset: 0,
          limit: 5,
          truncated: options.params.path.flow_id === "0",
        },
    response: new Response("{}"),
  }));
  const result = {
    id: "r",
    context: { network_id: "n", snapshot_id: "s" },
  } as components["schemas"]["ResultEnvelope"];
  render(
    <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <TraceResults result={result} />
      </QueryClientProvider>
    </ConfigProvider>,
  );
  await screen.findByText("1. first-node");
  expect(screen.getByText(/未显示路径的结论未知/)).toBeTruthy();
  await userEvent.click(screen.getByRole("radio", { name: /路径 2/ }));
  await screen.findByText("1. acl-node");
  expect(screen.getByText("未知或扩展动作（FUTURE_ACTION）")).toBeTruthy();
  expect(screen.queryByText("1. first-node")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Flow 1" }));
  await screen.findByText("1. second-flow-node");
  expect(screen.queryByText("1. acl-node")).toBeNull();
  expect(screen.getAllByText(/没有路由/).length).toBeGreaterThan(0);
});
