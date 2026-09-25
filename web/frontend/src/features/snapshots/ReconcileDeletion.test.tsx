import { it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setSession } from "../../app/session";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { ReconcileDeletion } from "./ReconcileDeletion";
const job = {
  id: "fixed-job",
  kind: "deletion",
  status: "failed",
} as components["schemas"]["JobDTO"];
function view(role: "admin" | "member") {
  setSession({
    user_id: "u",
    username: "u",
    role,
    csrf_token: "c",
    must_change_password: false,
  });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ReconcileDeletion job={job} />
    </QueryClientProvider>,
  );
}
afterEach(() => {
  cleanup();
  setSession(null);
  vi.restoreAllMocks();
});
it("members can see unresolved state but cannot reconcile", () => {
  view("member");
  expect(screen.getByText("删除状态待对账")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "检查远端并对账" })).toBeNull();
});
it("reconciles the fixed job and displays actual returned resource state", async () => {
  const request = vi.spyOn(api, "POST").mockResolvedValue({
    data: { resource_id: "resource", state: "deleted" },
    response: new Response("{}"),
  } as never);
  view("admin");
  fireEvent.change(screen.getByLabelText("对账说明"), {
    target: { value: "已按运行手册核对引擎状态，现在确认资源是否仍然存在。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "检查远端并对账" }));
  await waitFor(() =>
    expect(screen.getByText("已确认远端删除，保留历史结果。")).toBeTruthy(),
  );
  expect(request).toHaveBeenCalledWith(
    "/api/v1/admin/deletions/{job_id}/reconcile",
    expect.objectContaining({ params: { path: { job_id: "fixed-job" } } }),
  );
  expect(request).toHaveBeenCalledTimes(1);
});
