import { useEffect, useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Providers } from "./App";
import { LoginPage } from "../features/auth/Auth";
import { palettes } from "./theme";

const preferenceKey = "batfish-theme-preference";
function luminance(hex: string) {
  const channels = [1, 3, 5]
    .map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
function contrast(a: string, b: string) {
  const [low, high] = [luminance(a), luminance(b)].sort((x, y) => x - y);
  return (high + 0.05) / (low + 0.05);
}
it("keeps text and necessary input boundaries readable in both themes", () => {
  for (const p of Object.values(palettes)) {
    for (const foreground of [p.text, p.muted, p.accent, p.cyan]) {
      for (const background of [p.panel, p.raised, p.input])
        expect(contrast(foreground, background)).toBeGreaterThanOrEqual(4.5);
    }
    expect(contrast(p.border, p.input)).toBeGreaterThanOrEqual(3);
    expect(contrast(p.good, p.goodBg)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(p.warning, p.warningBg)).toBeGreaterThanOrEqual(4.5);
  }
  expect(contrast("#ffffff", "#4158d7")).toBeGreaterThanOrEqual(4.5);
});
let dark = false;
let changes: Set<() => void>;
beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  dark = false;
  changes = new Set();
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
    matches: query === "(prefers-color-scheme: dark)" && dark,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: (
      _event: string,
      listener: EventListenerOrEventListenerObject,
    ) => {
      if (query === "(prefers-color-scheme: dark)")
        changes.add(listener as () => void);
    },
    removeEventListener: (
      _event: string,
      listener: EventListenerOrEventListenerObject,
    ) => {
      if (query === "(prefers-color-scheme: dark)")
        changes.delete(listener as () => void);
    },
    dispatchEvent: () => true,
  }));
});
afterEach(() => vi.restoreAllMocks());
function mount(children?: React.ReactNode) {
  return render(
    <Providers>
      <MemoryRouter>
        <LoginPage />
        {children}
      </MemoryRouter>
    </Providers>,
  );
}
function systemChange(value: boolean) {
  dark = value;
  act(() => changes.forEach((notify) => notify()));
}
it("follows the system until explicitly chosen, and can return to system", () => {
  mount();
  expect(document.documentElement.dataset.theme).toBe("light");
  systemChange(true);
  expect(document.documentElement.dataset.theme).toBe("dark");
  fireEvent.click(screen.getByRole("button", { name: "浅色主题" }));
  systemChange(false);
  systemChange(true);
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(localStorage.getItem(preferenceKey)).toBe("light");
  fireEvent.click(screen.getByRole("button", { name: "跟随系统" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem(preferenceKey)).toBe("system");
});
it("restores a persisted choice and exposes the selected control", () => {
  localStorage.setItem(preferenceKey, "dark");
  mount();
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(
    screen
      .getByRole("button", { name: "深色主题" })
      .getAttribute("aria-pressed"),
  ).toBe("true");
});
it("falls back from a damaged preference without blocking login", () => {
  localStorage.setItem(preferenceKey, "invalid");
  dark = true;
  mount();
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(screen.getByRole("heading", { name: "登录工作台" })).toBeTruthy();
});
it("continues switching when browser storage is unavailable", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("disabled");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("disabled");
  });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "深色主题" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  fireEvent.click(screen.getByRole("button", { name: "浅色主题" }));
  expect(document.documentElement.dataset.theme).toBe("light");
});
it("keeps form state, cache identity and mounted children on theme switches", () => {
  const mounts = vi.fn();
  const clients = new Set();
  function Draft() {
    const [draft, setDraft] = useState("");
    clients.add(useQueryClient());
    useEffect(mounts, []);
    return (
      <input
        aria-label="未提交条件"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
    );
  }
  mount(<Draft />);
  fireEvent.change(screen.getByLabelText("未提交条件"), {
    target: { value: "10.0.0.0/24" },
  });
  fireEvent.click(screen.getByRole("button", { name: "深色主题" }));
  fireEvent.click(screen.getByRole("button", { name: "浅色主题" }));
  expect((screen.getByLabelText("未提交条件") as HTMLInputElement).value).toBe(
    "10.0.0.0/24",
  );
  expect(clients.size).toBe(1);
  expect(mounts).toHaveBeenCalledTimes(1);
});
