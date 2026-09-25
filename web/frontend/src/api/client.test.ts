import { it, expect, vi, afterEach } from "vitest";
import { createClient, unwrap } from "./client";
import { setSession } from "../app/session";
afterEach(() => setSession(null));
it("sends cookies and memory CSRF only to same-origin API", async () => {
  setSession({
    user_id: "u",
    username: "member",
    role: "member",
    csrf_token: "ephemeral",
    must_change_password: false,
  });
  const requests: Request[] = [];
  const client = createClient(async (request) => {
    requests.push(request as Request);
    return new Response("{}", {
      headers: { "Content-Type": "application/json" },
    });
  });
  await client.POST("/api/v1/auth/logout");
  expect(requests[0].credentials).toBe("same-origin");
  expect(requests[0].headers.get("X-CSRF-Token")).toBe("ephemeral");
  expect(localStorage.length).toBe(0);
});
it("hides arbitrary server error contents", async () => {
  await expect(
    unwrap(
      Promise.resolve({
        error: "<html>secret stack</html>",
        response: new Response(null, { status: 500 }),
      }),
    ),
  ).rejects.toMatchObject({ message: "服务暂时不可用，请稍后重试。" });
});
it("ignores an expired response from a previous identity", async () => {
  const { getSession } = await import("../app/session");
  let finish!: (response: Response) => void;
  const pending = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  setSession({
    user_id: "old",
    username: "old",
    role: "member",
    csrf_token: "old",
    must_change_password: false,
  });
  const client = createClient(async () => pending);
  const response = client.GET("/api/v1/auth/me");
  await vi.waitFor(() => expect(finish).toBeTypeOf("function"));
  setSession({
    user_id: "new",
    username: "new",
    role: "member",
    csrf_token: "new",
    must_change_password: false,
  });
  finish(
    new Response("{}", {
      status: 401,
      headers: { "Content-Type": "application/json" },
    }),
  );
  await response;
  expect(getSession()?.user_id).toBe("new");
});
