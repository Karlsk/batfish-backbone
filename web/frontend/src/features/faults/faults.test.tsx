import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FaultsPage } from "./FaultsPage";

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
            { id: "baseline", display_name: "原始基线", status: "ready" },
            { id: "candidate", display_name: "派生候选", status: "ready" },
          ],
        },
      ],
    },
    isFetching: false,
    hasNextPage: false,
  }),
}));
vi.mock("../inventory/useCandidates", () => ({
  useCandidates: () => ({
    nodes: ["c1", "c2"],
    interfaces: (names: string[]) =>
      names.includes("c1") ? ["GigabitEthernet0/0"] : ["GigabitEthernet0/1"],
    controls: <div>真实候选已加载</div>,
  }),
}));

afterEach(() => vi.clearAllMocks());

function shell() {
  return render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <FaultsPage />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
}

async function chooseBaseline() {
  await userEvent.click(screen.getByRole("combobox", { name: "基线快照" }));
  await userEvent.click(screen.getByRole("option", { name: "原始基线" }));
}

it("previews a deduplicated model outage and never edits the baseline", async () => {
  shell();
  await chooseBaseline();
  await userEvent.click(screen.getByRole("combobox", { name: "接口所在设备" }));
  await userEvent.click(screen.getByRole("option", { name: "c1" }));
  await userEvent.click(screen.getByRole("combobox", { name: "接口名称" }));
  await userEvent.click(
    screen.getByRole("option", { name: "GigabitEthernet0/0" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "加入接口" }));
  expect(screen.getByText("c1 · GigabitEthernet0/0")).toBeTruthy();
  await userEvent.click(screen.getByRole("combobox", { name: "停用设备" }));
  await userEvent.click(screen.getAllByRole("option", { name: "c1" }).at(-1)!);
  expect(screen.queryByText("c1 · GigabitEthernet0/0")).toBeNull();
  expect(screen.getByText(/原始基线保持不变/)).toBeTruthy();
  expect(screen.getByText(/仅在 Batfish 模型中模拟/)).toBeTruthy();
});

it("double click submits one frozen scenario with one idempotency key", async () => {
  let resolve!: (value: unknown) => void;
  mocks.post.mockReturnValue(new Promise((done) => (resolve = done)));
  shell();
  await chooseBaseline();
  await userEvent.type(
    screen.getByRole("textbox", { name: "方案名称" }),
    "断开 c1",
  );
  await userEvent.click(screen.getByRole("combobox", { name: "停用设备" }));
  await userEvent.click(screen.getByRole("option", { name: "c1" }));
  const submit = screen.getByRole("button", { name: "创建派生快照" });
  fireEvent.click(submit);
  fireEvent.click(submit);
  expect(mocks.post).toHaveBeenCalledTimes(1);
  expect(mocks.post.mock.calls[0][1].body).toEqual({
    display_name: "断开 c1",
    deactivate_nodes: ["c1"],
    deactivate_interfaces: [],
  });
  expect(
    mocks.post.mock.calls[0][1].params.header["idempotency-key"],
  ).toBeTruthy();
  resolve({
    data: { snapshot_id: "derived", job_id: "job" },
    response: new Response("{}"),
  });
  await waitFor(() => expect(screen.getByText(/派生任务/)).toBeTruthy());
});

it("failed or unknown engine jobs never advertise completed impact analysis", async () => {
  mocks.post.mockResolvedValue({
    data: { snapshot_id: "derived", job_id: "job" },
    response: new Response("{}"),
  });
  mocks.get.mockResolvedValue({
    data: {
      id: "job",
      status: "interrupted",
      error: { code: "ENGINE_STATE_UNKNOWN", request_id: "request" },
    },
    response: new Response("{}"),
  });
  shell();
  await chooseBaseline();
  await userEvent.type(
    screen.getByRole("textbox", { name: "方案名称" }),
    "测试",
  );
  await userEvent.click(screen.getByRole("combobox", { name: "停用设备" }));
  await userEvent.click(screen.getByRole("option", { name: "c2" }));
  await userEvent.click(screen.getByRole("button", { name: "创建派生快照" }));
  expect(await screen.findByText(/引擎状态待确认/)).toBeTruthy();
  expect(screen.queryByRole("link", { name: "进入影响分析" })).toBeNull();
  expect(screen.getByRole("link", { name: "查看任务详情" })).toBeTruthy();
});

it("opens a bounded comparison only after the derived snapshot is ready", async () => {
  mocks.post.mockResolvedValue({
    data: { snapshot_id: "derived", job_id: "job" },
    response: new Response("{}"),
  });
  let resolveSnapshot!: (value: unknown) => void;
  mocks.get.mockImplementation((path: string) =>
    path.includes("/jobs/")
      ? Promise.resolve({
          data: { id: "job", status: "succeeded" },
          response: new Response("{}"),
        })
      : new Promise((done) => {
          resolveSnapshot = done;
        }),
  );
  shell();
  await chooseBaseline();
  await userEvent.type(
    screen.getByRole("textbox", { name: "方案名称" }),
    "断开 c2",
  );
  await userEvent.click(screen.getByRole("combobox", { name: "停用设备" }));
  await userEvent.click(screen.getByRole("option", { name: "c2" }));
  await userEvent.click(screen.getByRole("button", { name: "创建派生快照" }));
  await waitFor(() => expect(resolveSnapshot).toBeTypeOf("function"));
  expect(screen.queryByRole("link", { name: "进入影响分析" })).toBeNull();
  resolveSnapshot({
    data: {
      id: "derived",
      status: "ready_with_warnings",
      base_snapshot_id: "baseline",
    },
    response: new Response("{}"),
  });
  const link = await screen.findByRole("link", { name: "进入影响分析" });
  expect(link.getAttribute("href")).toBe(
    "/changes?baseline=baseline&candidate=derived",
  );
  expect(screen.getByText(/仍需确认分析类型和范围/)).toBeTruthy();
  expect(screen.getByText(/派生快照包含解析或模型警告/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "查看派生快照诊断" })).toBeTruthy();
});
