import { afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { TopologyForm } from "./TopologyForm";
const mocks = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { POST: mocks.post },
}));
vi.mock("../../components/useDraftGuard", () => ({
  useDraftGuard: () => ({ holder: null, allowNavigation: () => {} }),
}));
vi.mock("../inventory/useCandidates", () => ({
  useCandidates: () => ({ nodes: [], controls: null }),
}));
afterEach(() => vi.clearAllMocks());
for (const rejected of [true, false])
  it(`topology ${rejected ? "known rejection unlocks" : "unknown outcome freezes"} request and preserves retry semantics`, async () => {
    if (rejected)
      mocks.post.mockResolvedValue({
        response: new Response(null, { status: 429 }),
        error: { error: { code: "RATE_LIMITED" } },
      });
    else mocks.post.mockRejectedValue(new TypeError("connection lost"));
    render(
      <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }}>
        <MemoryRouter>
          <TopologyForm networkId="n" snapshotId="s" />
        </MemoryRouter>
      </ConfigProvider>,
    );
    const submit = screen.getByRole("button", { name: "生成拓扑" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    await screen.findByText(
      rejected ? "操作过于频繁，请稍后重试。" : "服务暂时不可用，请稍后重试。",
    );
    expect(mocks.post).toHaveBeenCalledTimes(1);
    const initial = mocks.post.mock.calls[0][1];
    expect(initial.body.view).toBe("layer3");
    const input = screen.getByRole("combobox", {
      name: "关系视图",
    }) as HTMLInputElement;
    await waitFor(() => expect(input.disabled).toBe(!rejected));
    if (rejected) {
      await userEvent.click(input);
      await userEvent.click(screen.getByRole("option", { name: "BGP 关系" }));
    }
    await waitFor(() =>
      expect(submit.classList.contains("ant-btn-loading")).toBe(false),
    );
    fireEvent.click(submit);
    await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(2));
    const retry = mocks.post.mock.calls[1][1];
    if (rejected) {
      expect(retry.params.header["idempotency-key"]).not.toBe(
        initial.params.header["idempotency-key"],
      );
      expect(retry.body.view).toBe("bgp");
    } else {
      expect(retry).toEqual(initial);
    }
  });
