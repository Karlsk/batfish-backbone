import userEvent from "@testing-library/user-event";
import { it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { pollInterval, canCancel, durationLabel } from "./model";
import { JobDetail } from "./Jobs";
import { setSession } from "../../app/session";
import type { components } from "../../api/schema";
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../api/client", async (original) => {
  const actual = await original<typeof import("../../api/client")>();
  return { ...actual, api: { GET: mocks.get, POST: mocks.post } };
});
const job = {
  id: "j",
  kind: "initialization",
  resource_ids: { network_id: "n", snapshot_id: "s" },
  requested_parameters: {},
  effective_parameters: {},
  created_by: "u",
  status: "running",
  phase: "querying",
  attempt: 1,
  engine_state: "busy",
  cancel_allowed: false,
  created_at: "2026-09-25T00:00:00Z",
} as components["schemas"]["JobDTO"];
afterEach(() => {
  setSession(null);
  vi.clearAllMocks();
});
it("terminal jobs stop polling; active jobs back off without a fake percentage", () => {
  expect(pollInterval({ ...job, status: "succeeded" })).toBe(false);
  expect(pollInterval({ ...job, created_at: new Date().toISOString() })).toBe(
    2000,
  );
  expect(pollInterval(job)).toBe(5000);
});
it("running is never cancellable even if a stale flag says otherwise", () => {
  expect(
    canCancel(
      { ...job, cancel_allowed: true },
      { user_id: "u", role: "member" },
    ),
  ).toBe(false);
  expect(
    canCancel(
      { ...job, status: "queued", cancel_allowed: true },
      { user_id: "other", role: "member" },
    ),
  ).toBe(false);
});
it("unmounting a running job does not cancel it", async () => {
  setSession({
    user_id: "u",
    username: "u",
    role: "member",
    csrf_token: "csrf",
    must_change_password: false,
  });
  mocks.get.mockResolvedValue({ data: job, response: new Response("{}") });
  const view = render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/jobs/j"]}>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByText("执行中", { exact: true });
  expect(screen.queryByRole("button", { name: "取消排队" })).toBeNull();
  view.unmount();
  expect(mocks.post).not.toHaveBeenCalled();
});
it("a queued cancellation race explains 409 and refreshes to running", async () => {
  setSession({
    user_id: "u",
    username: "u",
    role: "member",
    csrf_token: "csrf",
    must_change_password: false,
  });
  mocks.get
    .mockResolvedValueOnce({
      data: { ...job, status: "queued", cancel_allowed: true },
      response: new Response("{}"),
    })
    .mockResolvedValue({ data: job, response: new Response("{}") });
  mocks.post.mockResolvedValue({
    error: { error: { code: "CONFLICT", request_id: "race" } },
    response: new Response("{}", { status: 409 }),
  });
  const view = render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/jobs/j"]}>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "取消排队" }),
  );
  await screen.findByText("任务可能已被领取，无法取消排队；已刷新当前状态。");
  await screen.findByText("执行中", { exact: true });
  expect(screen.queryByRole("button", { name: "取消排队" })).toBeNull();
  expect(mocks.post).toHaveBeenCalledTimes(1);
  view.unmount();
});

it("uses actual start/end times rather than creation for execution duration", () => {
  expect(durationLabel({ ...job, started_at: null })).toBe("尚未开始");
  expect(
    durationLabel({
      ...job,
      started_at: "2026-09-25T01:00:00Z",
      finished_at: "2026-09-25T01:01:05Z",
    }),
  ).toBe("1 分 5 秒");
});
