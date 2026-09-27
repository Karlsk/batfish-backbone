import { afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../../api/schema";
import { ChangeResults, ChangesPage } from "./ChangesPage";

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get, POST: mocks.post },
}));
vi.mock("../../app/context", async (original) => ({
  ...(await original<typeof import("../../app/context")>()),
  useResourceContext: () => ({ network: { id: "network", name: "测试网络" } }),
}));
vi.mock("../networks/queries", () => ({
  useSnapshots: () => ({
    data: {
      pages: [
        {
          items: [
            { id: "baseline", display_name: "基线", status: "ready" },
            { id: "candidate", display_name: "候选", status: "ready" },
          ],
        },
      ],
    },
    isFetching: false,
  }),
}));
afterEach(() => vi.clearAllMocks());
const comparison = (
  id: string,
  baseline = "baseline",
  candidate = "candidate",
) =>
  ({
    id,
    network_id: "network",
    baseline_snapshot_id: baseline,
    candidate_snapshot_id: candidate,
    display_name: "测试比较",
    coverage: "complete",
    coverage_notes: [],
  }) as unknown as components["schemas"]["ComparisonDTO"];
function shell(node: React.ReactNode, path = "/") {
  return render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter initialEntries={[path]}>
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

it("prefills fault comparison direction without creating or analyzing automatically", async () => {
  mocks.get.mockResolvedValue({
    data: { items: [], offset: 0, limit: 20, total: 0 },
    response: new Response("{}"),
  });
  mocks.post.mockResolvedValue({
    data: comparison("fault-comparison"),
    response: new Response("{}"),
  });
  shell(<ChangesPage />, "/changes?baseline=baseline&candidate=candidate");
  expect(await screen.findByText(/已带入故障方案的原始基线/)).toBeTruthy();
  expect(mocks.post).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "创建比较" }));
  await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
  expect(mocks.post.mock.calls[0][1].body).toMatchObject({
    baseline_snapshot_id: "baseline",
    candidate_snapshot_id: "candidate",
  });
  expect(await screen.findByText("基线：基线")).toBeTruthy();
  expect(screen.getByText("候选：候选")).toBeTruthy();
  await userEvent.click(screen.getByRole("tab", { name: "可达性变化" }));
  expect(screen.getByRole("button", { name: "分析可达性变化" })).toHaveProperty(
    "disabled",
    true,
  );
});

it("exchanging two snapshots creates a new immutable direction", async () => {
  mocks.get.mockResolvedValue({
    data: { items: [], offset: 0, limit: 50, total: 0 },
    response: new Response("{}"),
  });
  mocks.post.mockResolvedValue({
    data: comparison("new", "candidate", "baseline"),
    response: new Response("{}"),
  });
  shell(<ChangesPage />);
  await userEvent.click(screen.getByRole("combobox", { name: "基线快照" }));
  await userEvent.click(screen.getAllByRole("option", { name: "基线" })[0]);
  await userEvent.click(screen.getByRole("combobox", { name: "候选快照" }));
  await userEvent.click(
    screen.getAllByRole("option", { name: "候选" }).at(-1)!,
  );
  await userEvent.click(screen.getByRole("button", { name: "交换基线与候选" }));
  await userEvent.click(screen.getByRole("button", { name: "创建比较" }));
  await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
  expect(mocks.post.mock.calls[0][1].body).toMatchObject({
    baseline_snapshot_id: "candidate",
    candidate_snapshot_id: "baseline",
  });
  expect(await screen.findByText("基线：候选")).toBeTruthy();
  expect(screen.getByText("候选：基线")).toBeTruthy();
});

it("explains engine or SDK version mismatch distinctly from an empty comparison", async () => {
  mocks.get.mockResolvedValue({
    data: { items: [], offset: 0, limit: 20, total: 0 },
    response: new Response("{}"),
  });
  mocks.post.mockResolvedValue({
    error: {
      error: {
        code: "CONFLICT",
        field_errors: [
          {
            path: ["body", "candidate_snapshot_id"],
            message: "Snapshot engine or SDK versions differ",
          },
        ],
      },
    },
    response: new Response("{}", { status: 409 }),
  });
  shell(<ChangesPage />);
  await userEvent.click(screen.getByRole("combobox", { name: "基线快照" }));
  await userEvent.click(screen.getAllByRole("option", { name: "基线" })[0]);
  await userEvent.click(screen.getByRole("combobox", { name: "候选快照" }));
  await userEvent.click(
    screen.getAllByRole("option", { name: "候选" }).at(-1)!,
  );
  await userEvent.click(screen.getByRole("button", { name: "创建比较" }));
  expect(await screen.findByText(/引擎或 SDK 版本不同/)).toBeTruthy();
  expect(screen.getByText("尚无比较记录")).toBeTruthy();
});

it("requires an explicit reachability scope and never reuses old comparison evidence", async () => {
  mocks.get.mockImplementation(async (path, args) => {
    if (path.includes("/comparisons") && !path.includes("/analyses"))
      return {
        data: {
          items: [
            comparison("old"),
            comparison("new", "candidate", "baseline"),
          ],
          offset: 0,
          limit: 50,
          total: 2,
        },
        response: new Response("{}"),
      };
    if (path.includes("/results/"))
      return {
        data: { columns: [], rows: [], total: 0, offset: 0, limit: 20 },
        response: new Response("{}"),
      };
    return {
      data: { id: args?.params?.path?.job_id },
      response: new Response("{}"),
    };
  });
  mocks.post.mockResolvedValue({
    data: { id: "job-new", status: "queued" },
    response: new Response("{}"),
  });
  shell(<ChangesPage />);
  await userEvent.click(
    await screen.findByRole("button", { name: /选择比较 old/ }),
  );
  await userEvent.click(screen.getByRole("tab", { name: "可达性变化" }));
  const submit = screen.getByRole("button", { name: "分析可达性变化" });
  expect((submit as HTMLButtonElement).disabled).toBe(true);
  await userEvent.type(
    screen.getByRole("textbox", { name: "目的 IPv4 范围" }),
    "10.64.0.4",
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "起点设备或接口" }),
    "c1",
  );
  expect((submit as HTMLButtonElement).disabled).toBe(false);
  await userEvent.click(submit);
  await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
  expect(mocks.post.mock.calls[0][1].body).toMatchObject({
    destination_ips: "10.64.0.4",
    start_location: "c1",
  });
  expect(await screen.findByText("job-new")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: /选择比较 new/ }));
  expect(screen.queryByText("job-new")).toBeNull();
  expect(screen.getByText("基线：候选")).toBeTruthy();
});

it("loads configuration file details only after selection and keeps baseline left", async () => {
  const result = {
    id: "config-result",
    kind: "diff",
    context: {
      network_id: "network",
      snapshot_id: "candidate",
      reference_snapshot_id: "baseline",
    },
    effective_parameters: { operation: "config-diff" },
    summary: { returned_files: 1 },
    warnings: [],
    coverage: "complete",
    truncated: false,
  } as unknown as components["schemas"]["ResultEnvelope"];
  mocks.get.mockImplementation(async (path) => ({
    data: path.endsWith("/diff/files")
      ? {
          items: [
            {
              file_id: "file",
              path: "configs/c1.cfg",
              change: "changed",
              baseline_sha256: "old",
              candidate_sha256: "new",
              detail_truncated: false,
            },
          ],
          offset: 0,
          limit: 20,
          total: 1,
          truncated: false,
        }
      : {
          file: { file_id: "file", path: "configs/c1.cfg" },
          hunks: [
            {
              tag: "replace",
              baseline_lines: [{ number: 1, text: "old line" }],
              candidate_lines: [{ number: 1, text: "new line" }],
            },
          ],
          offset: 0,
          limit: 20,
          total: 1,
          truncated: false,
        },
    response: new Response("{}"),
  }));
  shell(<ChangeResults comparison={comparison("one")} result={result} />);
  expect(await screen.findByText("configs/c1.cfg")).toBeTruthy();
  expect(mocks.get).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "查看两侧文本" }));
  expect(await screen.findByText(/1: old line/)).toBeTruthy();
  expect(screen.getByText(/1: new line/)).toBeTruthy();
  const sides = screen.getByText("基线（左）").closest("div")?.parentElement;
  expect(sides?.textContent?.indexOf("old line")).toBeLessThan(
    sides?.textContent?.indexOf("new line") ?? 0,
  );
});

it("shows route direction in text alongside both next hops", async () => {
  const result = {
    id: "route-result",
    kind: "table",
    context: {
      network_id: "network",
      snapshot_id: "candidate",
      reference_snapshot_id: "baseline",
    },
    effective_parameters: { operation: "routes-diff" },
    summary: { returned_rows: 2 },
    warnings: [],
    coverage: "complete",
    truncated: false,
  } as unknown as components["schemas"]["ResultEnvelope"];
  mocks.get.mockResolvedValue({
    data: {
      rows: [
        {
          Change: "added",
          Node: "c1",
          Network: "10.0.0.0/24",
          Reference_Next_Hop: null,
          Snapshot_Next_Hop: "c2",
        },
        {
          Change: "removed",
          Node: "c1",
          Network: "10.1.0.0/24",
          Reference_Next_Hop: "c3",
          Snapshot_Next_Hop: null,
        },
      ],
      columns: [],
      offset: 0,
      limit: 20,
      total: 2,
    },
    response: new Response("{}"),
  });
  shell(<ChangeResults comparison={comparison("one")} result={result} />);
  expect(await screen.findByText("候选新增")).toBeTruthy();
  expect(screen.getByText("候选消失")).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "基线下一跳" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "候选下一跳" })).toBeTruthy();
});

it("labels candidate direction and bounded empty results without a network-wide claim", async () => {
  const result = {
    id: "result",
    kind: "table",
    context: {
      network_id: "network",
      snapshot_id: "candidate",
      reference_snapshot_id: "baseline",
    },
    effective_parameters: { operation: "reachability-diff" },
    summary: {
      returned_rows: 0,
      count_scope: "sdk_witness_rows_not_all_business_flows",
    },
    warnings: [],
    coverage: "limited",
    truncated: true,
    truncation_reason: "trace_limit",
  } as unknown as components["schemas"]["ResultEnvelope"];
  mocks.get.mockResolvedValue({
    data: { columns: [], rows: [], total: 0, offset: 0, limit: 20 },
    response: new Response("{}"),
  });
  shell(<ChangeResults comparison={comparison("one")} result={result} />);
  expect(await screen.findByText(/所选条件内未发现可达性变化/)).toBeTruthy();
  expect(screen.getByText(/模型覆盖有限/)).toBeTruthy();
  expect(screen.getByText(/证据已截断/)).toBeTruthy();
  expect(screen.queryByText("全网无影响", { exact: true })).toBeNull();
});
