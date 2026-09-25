import { it, expect, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminOnly } from "./Access";
import { UserMutationError } from "./Users";
import { setSession } from "../../app/session";
import { ApiError } from "../../api/client";
afterEach(() => setSession(null));
it("member cannot enter administration", () => {
  setSession({
    user_id: "u",
    username: "u",
    role: "member",
    must_change_password: false,
    csrf_token: "csrf",
  });
  render(
    <MemoryRouter>
      <AdminOnly>
        <button>创建用户</button>
      </AdminOnly>
    </MemoryRouter>,
  );
  expect(screen.queryByRole("button", { name: "创建用户" })).toBeNull();
  expect(screen.getByText("当前账号没有操作权限。")).toBeTruthy();
});
it("renders server 403 even if UI had administration access", () => {
  render(<UserMutationError error={new ApiError("FORBIDDEN")} />);
  expect(screen.getByText("当前账号没有操作权限。")).toBeTruthy();
});

it("explains last administrator conflict", () => {
  render(
    <UserMutationError error={new ApiError("CONFLICT")} operation="edit" />,
  );
  expect(screen.getByText(/至少一位启用的管理员/)).toBeTruthy();
});
