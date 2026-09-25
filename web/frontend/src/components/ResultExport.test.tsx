import { it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { ResultExport } from "./ResultExport";
import { api } from "../api/client";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("offers CSV only for tables and never starts downloads on render", () => {
  const get = vi.spyOn(api, "GET");
  const view = render(
    <ResultExport result={{ id: "fixed-result", kind: "traces" }} />,
  );
  expect(screen.queryByRole("button", { name: "下载 CSV" })).toBeNull();
  expect(screen.getByText(/路径结果仅支持 JSON/)).toBeTruthy();
  expect(get).not.toHaveBeenCalled();
  view.rerender(
    <ResultExport result={{ id: "fixed-result", kind: "table" }} />,
  );
  expect(screen.getByRole("button", { name: "下载 CSV" })).toBeTruthy();
});
it("shows safe failure without downloading an error body", async () => {
  vi.spyOn(api, "GET").mockResolvedValue({
    error: { error: { code: "NOT_FOUND" } },
    response: new Response(null, { status: 404 }),
  } as never);
  render(<ResultExport result={{ id: "fixed-result", kind: "table" }} />);
  fireEvent.click(screen.getByRole("button", { name: "下载 JSON" }));
  await waitFor(() =>
    expect(screen.getByText("资源不存在或已被移除。")).toBeTruthy(),
  );
});
