import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FilterTestPage } from "./FilterTest";
import {
  buildFilterSearch,
  buildRuleReachability,
  defaultSearchDraft,
  defaultReachabilityDraft,
  filterDraftFromWitness,
} from "./advanced-requests";

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get, POST: mocks.post },
}));
vi.mock("../../app/context", async (original) => ({
  ...(await original<typeof import("../../app/context")>()),
  useResourceContext: () => ({
    network: { id: "network", name: "Network" },
    snapshot: { id: "snapshot", name: "Snapshot" },
  }),
}));
vi.mock("../inventory/useCandidates", () => ({
  useCandidates: () => ({ nodes: ["c2"], controls: null }),
}));
vi.mock("../../components/useDraftGuard", () => ({
  useDraftGuard: () => ({ holder: null, allowNavigation: () => {} }),
}));

describe("ACL advanced requests", () => {
  it("keeps search and reachability parameters separate", () => {
    const search = buildFilterSearch({
      ...defaultSearchDraft(),
      nodes: ["c2"],
      filters: ["WEB-SEARCH"],
      source: "10.64.0.1",
      destination: "10.64.0.2",
      action: "match_line",
      lineNumber: "2",
      protocols: ["tcp"],
      sourcePorts: "12345",
      destinationPorts: "443",
    });
    expect(search).toEqual({
      nodes: { mode: "literal", values: ["c2"] },
      filters: { mode: "literal", values: ["WEB-SEARCH"] },
      action: "match_line",
      options: {
        headers: {
          source_ip: "10.64.0.1",
          destination_ip: "10.64.0.2",
          ip_protocols: ["tcp"],
          source_ports: [12345],
          destination_ports: [443],
        },
        line_number: 2,
      },
    });
    const reach = buildRuleReachability({
      ...defaultReachabilityDraft(),
      nodes: ["c2"],
      filters: ["WEB-SEARCH"],
      ignoreComposites: false,
    });
    expect(reach).toEqual({
      nodes: { mode: "literal", values: ["c2"] },
      filters: { mode: "literal", values: ["WEB-SEARCH"] },
      options: { ignore_composites: false },
    });
    expect(JSON.stringify(reach)).not.toContain("headers");
    expect(JSON.stringify(search)).not.toContain("ignore_composites");
  });

  it("rejects unbounded scope and mismatched transport or line number", () => {
    const base = {
      ...defaultSearchDraft(),
      nodes: ["c2"],
      filters: ["WEB-SEARCH"],
      source: "10.64.0.1",
      destination: "10.64.0.2",
    };
    expect(() => buildFilterSearch({ ...base, nodes: [] })).toThrow("设备");
    expect(() => buildFilterSearch({ ...base, filters: [] })).toThrow("ACL");
    expect(() =>
      buildFilterSearch({ ...base, nodes: Array(11).fill("c2") }),
    ).toThrow("10");
    expect(() =>
      buildFilterSearch({ ...base, destinationPorts: "443" }),
    ).toThrow("TCP");
    expect(() => buildFilterSearch({ ...base, action: "match_line" })).toThrow(
      "规则行号",
    );
    expect(() =>
      buildRuleReachability({ ...defaultReachabilityDraft(), nodes: ["c2"] }),
    ).toThrow("ACL");
  });
});

describe("search witness handoff", () => {
  const preset = {
    networkId: "network",
    snapshotId: "snapshot",
    node: "c2",
    filter: "WEB-SEARCH",
    flow: {
      srcIp: "10.64.0.1",
      dstIp: "10.64.0.2",
      ipProtocol: "TCP",
      srcPort: 12345,
      dstPort: 443,
    },
  };
  it("keeps actual protocol, IPs, ports and selected ACL", () => {
    expect(filterDraftFromWitness(preset, "network", "snapshot")).toMatchObject(
      {
        node: "c2",
        filter: "WEB-SEARCH",
        source: "10.64.0.1",
        destination: "10.64.0.2",
        protocols: ["tcp"],
        sourcePorts: "12345",
        destinationPorts: "443",
      },
    );
  });
  it("rejects a different snapshot or unsupported protocol", () => {
    expect(filterDraftFromWitness(preset, "network", "other")).toBeNull();
    expect(
      filterDraftFromWitness(
        { ...preset, flow: { ...preset.flow, ipProtocol: "IP" } },
        "network",
        "snapshot",
      ),
    ).toBeNull();
  });
});

it("keeps ACL search and rule diagnosis in independent tabs", async () => {
  mocks.get.mockResolvedValue({
    data: [
      { id: "search-filters", enabled: true, defaults: { action: "permit" } },
      {
        id: "filter-line-reachability",
        enabled: true,
        defaults: { options: { ignore_composites: true } },
      },
    ],
    response: new Response("{}"),
  });
  const user = userEvent.setup();
  render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <FilterTestPage />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
  await user.click(screen.getByRole("tab", { name: "条件搜索" }));
  await user.type(
    await screen.findByRole("textbox", { name: "搜索源 IPv4 地址" }),
    "10.64.0.1",
  );
  await user.click(screen.getByRole("tab", { name: "规则诊断" }));
  expect(
    screen.queryByRole("textbox", { name: "搜索源 IPv4 地址" }),
  ).toBeNull();
  await user.click(screen.getByRole("tab", { name: "条件搜索" }));
  expect(
    (
      screen.getByRole("textbox", {
        name: "搜索源 IPv4 地址",
      }) as HTMLInputElement
    ).value,
  ).toBe("10.64.0.1");
});

it("keeps the active tab mounted while its job submission is unresolved", async () => {
  mocks.get.mockResolvedValue({
    data: [
      { id: "search-filters", enabled: true, defaults: { action: "permit" } },
    ],
    response: new Response("{}"),
  });
  mocks.post.mockImplementation(() => new Promise(() => {}));
  const user = userEvent.setup();
  render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <FilterTestPage />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
  await user.click(screen.getByRole("tab", { name: "条件搜索" }));
  await user.type(
    screen.getByRole("combobox", { name: "设备范围" }),
    "c2{enter}",
  );
  await user.type(
    screen.getByRole("combobox", { name: "ACL 范围" }),
    "WEB-SEARCH{enter}",
  );
  await user.type(
    screen.getByRole("textbox", { name: "搜索源 IPv4 地址" }),
    "10.64.0.1",
  );
  await user.type(
    screen.getByRole("textbox", { name: "搜索目标 IPv4 地址" }),
    "10.64.0.2",
  );
  await user.click(screen.getByRole("button", { name: "寻找示例流量" }));
  expect(mocks.post).toHaveBeenCalledOnce();
  expect(
    screen.getByRole("tab", { name: "规则诊断" }).getAttribute("aria-disabled"),
  ).toBe("true");
});
