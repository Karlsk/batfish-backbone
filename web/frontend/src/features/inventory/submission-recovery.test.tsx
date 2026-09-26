import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { AnalysisPage } from "./Analysis";
import { TracePage } from "../traceroute/TraceForm";

const mocks = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { POST: mocks.post },
}));
vi.mock("../../app/context", () => ({
  useResourceContext: () => ({
    network: { id: "n" },
    snapshot: { id: "s", name: "saved" },
  }),
}));
vi.mock("../../components/useDraftGuard", () => ({
  useDraftGuard: () => ({ holder: null, allowNavigation: () => {} }),
}));
vi.mock("./useCandidates", () => ({
  useCandidates: () => ({
    nodes: [],
    controls: null,
    interfaces: () => [],
    vrfs: () => [],
  }),
}));
afterEach(() => vi.clearAllMocks());

for (const kind of ["routes", "trace"] as const) {
  for (const rejected of [true, false]) {
    it(`${kind}: ${rejected ? "known queue rejection unlocks edits with a new key" : "uncertain failure keeps frozen draft and retry key"}`, async () => {
      if (rejected)
        mocks.post.mockResolvedValue({
          response: new Response(null, { status: 429 }),
          error: { error: { code: "RATE_LIMITED" } },
        });
      else mocks.post.mockRejectedValue(new TypeError("connection lost"));
      render(
        <ConfigProvider locale={zhCN}>
          <MemoryRouter initialEntries={["/analysis/routes"]}>
            <Routes>
              <Route
                path="/analysis/:operation"
                element={kind === "routes" ? <AnalysisPage /> : <TracePage />}
              />
            </Routes>
          </MemoryRouter>
        </ConfigProvider>,
      );
      if (kind === "trace") {
        fireEvent.click(screen.getByRole("radio", { name: "专家表达式" }));
        fireEvent.change(screen.getByRole("textbox", { name: "起点表达式" }), {
          target: { value: "r1" },
        });
      }
      const input = screen.getByRole("textbox", {
        name: kind === "routes" ? "IPv4 路由前缀" : "目标 IPv4 地址",
      }) as HTMLInputElement;
      fireEvent.change(input, {
        target: { value: kind === "routes" ? "10.0.0.0/24" : "10.0.0.2" },
      });
      const submit = screen.getByRole("button", {
        name: kind === "routes" ? "执行查询" : "推演路径",
      });
      fireEvent.click(submit);
      await screen.findByText(
        rejected
          ? "操作过于频繁，请稍后重试。"
          : "服务暂时不可用，请稍后重试。",
      );
      await waitFor(() => expect(input.disabled).toBe(!rejected));
      const initial = mocks.post.mock.calls[0][1];
      if (rejected)
        fireEvent.change(input, {
          target: { value: kind === "routes" ? "10.1.0.0/24" : "10.1.0.2" },
        });
      fireEvent.click(submit);
      await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(2));
      const retry = mocks.post.mock.calls[1][1];
      if (rejected) {
        expect(retry.params.header["idempotency-key"]).not.toBe(
          initial.params.header["idempotency-key"],
        );
        expect(retry.body).not.toEqual(initial.body);
      } else {
        expect(retry.params.header["idempotency-key"]).toBe(
          initial.params.header["idempotency-key"],
        );
        expect(retry.body).toEqual(initial.body);
      }
    });
  }
}
