import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { buildFilterTest, defaultFilterDraft } from "./requests";
import { aclDecision } from "./FilterResult";
import { FilterTestForm, isUnsupportedAcl } from "./FilterTest";
import { ApiError } from "../../api/client";

const mocks = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { POST: mocks.post, GET: mocks.get },
}));
vi.mock("../inventory/useCandidates", () => ({
  useCandidates: () => ({ nodes: ["c2"], controls: null }),
}));
vi.mock("../../components/useDraftGuard", () => ({
  useDraftGuard: () => ({ holder: null, allowNavigation: () => {} }),
}));
afterEach(() => vi.clearAllMocks());

it("recognizes unsupported ACL models without treating generic conflicts as coverage failures", () => {
  expect(
    isUnsupportedAcl(
      new ApiError("CONFLICT", "", [
        {
          path: ["snapshot_id"],
          message:
            "ACL verification is unsupported for Huawei/H3C in this model",
        },
      ]),
    ),
  ).toBe(true);
  expect(isUnsupportedAcl(new ApiError("CONFLICT"))).toBe(false);
});

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

describe("ACL flow request", () => {
  it("requires a device, ACL, and IPv4 pair", () => {
    const draft = defaultFilterDraft();
    expect(() => buildFilterTest(draft)).toThrow("设备");
    expect(() => buildFilterTest({ ...draft, node: "c2" })).toThrow("ACL");
    expect(() =>
      buildFilterTest({
        ...draft,
        node: "c2",
        filter: "WEB-TEST",
        source: "::1",
        destination: "10.64.0.2",
      }),
    ).toThrow("IPv4");
  });

  it("keeps exact literal selectors and typed transport options", () => {
    const request = buildFilterTest({
      ...defaultFilterDraft(),
      node: "c2",
      filter: "WEB-TEST",
      source: "10.64.0.1",
      destination: "10.64.0.2",
      protocols: ["tcp"],
      sourcePorts: "12345",
      destinationPorts: "443",
    });
    expect(request.nodes).toEqual({ mode: "literal", values: ["c2"] });
    expect(request.filters).toEqual({ mode: "literal", values: ["WEB-TEST"] });
    expect(request.options).toEqual({
      ip_protocols: ["tcp"],
      source_ports: [12345],
      destination_ports: [443],
    });
  });

  it("rejects port controls for ICMP and invalid ports", () => {
    const draft = {
      ...defaultFilterDraft(),
      node: "c2",
      filter: "WEB-TEST",
      source: "10.64.0.1",
      destination: "10.64.0.2",
    };
    expect(() =>
      buildFilterTest({ ...draft, destinationPorts: "443" }),
    ).toThrow("TCP");
    expect(() =>
      buildFilterTest({
        ...draft,
        protocols: ["tcp"],
        destinationPorts: "65536",
      }),
    ).toThrow("端口");
  });
});

describe("ACL result meaning", () => {
  it("does not turn no filter or unknown model action into a permit", () => {
    expect(aclDecision([]).kind).toBe("unknown");
    expect(aclDecision([{ Action: "UNSUPPORTED" }]).kind).toBe("unknown");
  });

  it("keeps implicit deny separate from source rule lines", () => {
    expect(
      aclDecision([
        {
          Action: "DENY",
          Implicit_Deny: true,
          Line_Content: "no-match",
          Source_References: [],
        },
      ]),
    ).toEqual({ kind: "deny", implicit: true, label: "隐式拒绝" });
  });

  it("does not summarize a partial page as universal permit", () => {
    expect(aclDecision([{ Action: "PERMIT" }], 2).kind).toBe("unknown");
    expect(aclDecision([{ Action: "PERMIT" }], 1, true).kind).toBe("unknown");
  });
});

it("loads ACL candidates in the selected snapshot and submits minimal flow", async () => {
  mocks.post.mockImplementation(async (path: string) => ({
    data: { id: path.endsWith("resolve-filters") ? "resolve-job" : "test-job" },
    response: new Response("{}"),
  }));
  mocks.get.mockImplementation(async (path: string) => ({
    data: path.includes("/jobs/")
      ? { status: "succeeded", result_id: "resolved-result" }
      : {
          rows: [{ Node: { name: "c2" }, Filter_Name: "WEB-TEST" }],
          total: 1,
          offset: 0,
          limit: 200,
          truncated: false,
        },
    response: new Response("{}"),
  }));
  const user = userEvent.setup();
  shell(<FilterTestForm networkId="network" snapshotId="snapshot" />);
  await user.click(screen.getByRole("combobox", { name: "设备" }));
  await user.click(screen.getByText("c2"));
  await user.click(screen.getByRole("button", { name: "加载此设备 ACL" }));
  await waitFor(() => expect(mocks.get).toHaveBeenCalled());
  await user.click(screen.getByRole("combobox", { name: "ACL" }));
  await user.click(await screen.findByText("WEB-TEST"));
  await user.type(
    screen.getByRole("textbox", { name: "源 IPv4 地址" }),
    "10.64.0.1",
  );
  await user.type(
    screen.getByRole("textbox", { name: "目标 IPv4 地址" }),
    "10.64.0.2",
  );
  await user.click(screen.getByRole("button", { name: "测试 ACL 流量" }));
  await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(2));
  const [path, args] = mocks.post.mock.calls[1];
  expect(path).toContain("/analyses/test-filters");
  expect(args.params.path).toEqual({
    network_id: "network",
    snapshot_id: "snapshot",
  });
  expect(args.body).toMatchObject({
    source_ip: "10.64.0.1",
    destination_ip: "10.64.0.2",
    nodes: { mode: "literal", values: ["c2"] },
    filters: { mode: "literal", values: ["WEB-TEST"] },
  });
});

it("keeps protocol and port values when advanced options collapse", async () => {
  const user = userEvent.setup();
  shell(<FilterTestForm networkId="network" snapshotId="snapshot" />);
  await user.click(screen.getByText("高级参数"));
  await user.click(screen.getByRole("combobox", { name: "IP 协议" }));
  await user.click(screen.getByText("TCP"));
  await user.type(screen.getByRole("textbox", { name: "目标端口" }), "443");
  await user.click(screen.getByText("高级参数"));
  await user.click(screen.getByText("高级参数"));
  expect(
    (screen.getByRole("textbox", { name: "目标端口" }) as HTMLInputElement)
      .value,
  ).toBe("443");
  expect(screen.getAllByText("TCP").length).toBeGreaterThan(0);
});
