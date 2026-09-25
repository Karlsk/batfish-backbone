import { afterEach, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { setSession } from "../../app/session";
import { AuthGuard, LogoutButton } from "./Auth";
vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    api: {
      POST: vi.fn(async () => ({
        data: undefined,
        response: new Response(null, { status: 204 }),
      })),
    },
  };
});
afterEach(() => setSession(null));
it("requires password change before any business page", () => {
  setSession({
    user_id: "u",
    username: "u",
    role: "member",
    must_change_password: true,
    csrf_token: "csrf",
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AuthGuard>
          <div>业务页面</div>
        </AuthGuard>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.queryByText("业务页面")).toBeNull();
  expect(screen.getByRole("heading", { name: "设置新密码" })).toBeTruthy();
});
it("logout clears cached resources", async () => {
  setSession({
    user_id: "u",
    username: "u",
    role: "member",
    must_change_password: false,
    csrf_token: "csrf",
  });
  const client = new QueryClient();
  client.setQueryData(["resource", "u", "n", "s"], "sensitive");
  render(
    <QueryClientProvider client={client}>
      <LogoutButton />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "退出登录" }));
  expect(client.getQueryCache().getAll()).toHaveLength(0);
});
