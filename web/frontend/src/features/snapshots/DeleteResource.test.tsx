import { it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ContextProvider } from "../../app/context";
import { setSession } from "../../app/session";
import { api } from "../../api/client";
import { DeleteResource } from "./DeleteResource";
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
      <MemoryRouter>
        <ContextProvider>
          <DeleteResource
            networkId="n"
            snapshotId="s"
            name="实验快照"
            state="ready"
          />
        </ContextProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => {
  cleanup();
  setSession(null);
  vi.restoreAllMocks();
});
it("hides deletion from ordinary members", () => {
  view("member");
  expect(screen.queryByRole("button", { name: "删除快照" })).toBeNull();
});
it("names the specific snapshot and requires confirmation before DELETE", async () => {
  const request = vi.spyOn(api, "DELETE").mockResolvedValue({
    error: { error: { code: "CONFLICT" } },
    response: new Response(null, { status: 409 }),
  } as never);
  view("admin");
  fireEvent.click(screen.getByRole("button", { name: "删除快照" }));
  expect(screen.getByText("实验快照")).toBeTruthy();
  expect(screen.getByText(/资源编号：s/)).toBeTruthy();
  expect(request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
  await waitFor(() =>
    expect(
      screen.getByText(/存在活动任务、未删除快照或待对账状态/),
    ).toBeTruthy(),
  );
  expect(request).toHaveBeenCalledTimes(1);
});
