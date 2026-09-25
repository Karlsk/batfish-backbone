import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SourceLines, sourceTarget } from "./Source";
it("does not invent a location for missing files or line numbers", () => {
  expect(
    sourceTarget({ file_id: null, path: "missing.cfg", lines: [9] }),
  ).toBeNull();
  expect(sourceTarget({ file_id: "f", path: "r.cfg", lines: [] })).toEqual({
    fileId: "f",
    path: "r.cfg",
    lines: [],
    offset: 0,
  });
  expect(
    sourceTarget({ file_id: "f", path: "r.cfg", lines: [0, -3, 8] }),
  ).toEqual({ fileId: "f", path: "r.cfg", lines: [8], offset: 2 });
});
it("highlights only returned actual line numbers that were supplied", () => {
  const { container } = render(
    <SourceLines
      lines={[
        { number: 1, text: "hostname r", truncated: false },
        { number: 8, text: "unknown command", truncated: false },
      ]}
      highlights={[8, 99]}
    />,
  );
  expect(container.querySelectorAll('[data-highlight="true"]')).toHaveLength(1);
  expect(screen.getByText("unknown command")).toBeTruthy();
  expect(
    container.querySelector('[data-line="1"]')?.getAttribute("data-highlight"),
  ).toBe("false");
});
