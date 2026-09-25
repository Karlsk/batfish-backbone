import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResultTable } from "./Results";
import { cellText } from "./cells";
import type { components } from "../../api/schema";
const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get },
}));
afterEach(() => vi.clearAllMocks());
const envelope = (id: string, snapshot: string) =>
  ({
    id,
    context: { network_id: "n", snapshot_id: snapshot },
  }) as components["schemas"]["ResultEnvelope"];
it("paginates and filters saved rows, then clears old content on result/context change", async () => {
  mocks.get.mockImplementation(async (_path, options) => {
    const { offset, filters } = options.params.query;
    const id = options.params.path.result_id;
    return {
      data: {
        columns: [{ key: "Hostname", label: "Hostname", type: "String" }],
        rows: [{ Hostname: `${id}-${offset}-${filters ? "filtered" : "all"}` }],
        offset,
        limit: 20,
        total: 41,
        truncated: false,
      },
      response: new Response("{}"),
    };
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const element = (id: string, snapshot: string) => (
    <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }}>
      <QueryClientProvider client={client}>
        <ResultTable
          key={`${id}:${snapshot}`}
          result={envelope(id, snapshot)}
        />
      </QueryClientProvider>
    </ConfigProvider>
  );
  const view = render(element("first", "s1"));
  await screen.findByText("first-0-all");
  await userEvent.click(screen.getByTitle("下一页"));
  await screen.findByText("first-20-all");
  expect(screen.queryByText("first-0-all")).toBeNull();
  await userEvent.click(screen.getByRole("combobox", { name: "结果筛选列" }));
  await userEvent.click(await screen.findByRole("option", { name: "主机名" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: "结果筛选值" }),
    "r1",
  );
  await userEvent.click(screen.getByRole("button", { name: "应用筛选" }));
  await screen.findByText("first-0-filtered");
  view.rerender(element("second", "s2"));
  await screen.findByText("second-0-all");
  expect(screen.queryByText("first-0-filtered")).toBeNull();
  expect(
    (screen.getByRole("textbox", { name: "结果筛选值" }) as HTMLInputElement)
      .value,
  ).toBe("");
});
it("renders next-hop variants without inventing an IP or hiding unknown types", () => {
  expect(cellText({ type: "discard" })).toContain("丢弃");
  expect(
    cellText({ type: "interface", interface: "Eth0", ip: "192.0.2.1" }),
  ).toBe("Eth0 → 192.0.2.1");
  expect(cellText({ type: "vrf", vrf: "BLUE" })).toBe("转入 VRF BLUE");
  expect(cellText({ type: "future", data: 3 })).toContain("future");
});
