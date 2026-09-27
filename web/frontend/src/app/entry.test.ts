import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { chooseEntry, preferredEntryPath } from "./entry";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

it("keeps the technical workspace as the default until a user chooses otherwise", () => {
  expect(preferredEntryPath()).toBe("/");
  chooseEntry("leader");
  expect(preferredEntryPath()).toBe("/leader/overview");
  chooseEntry("technical");
  expect(preferredEntryPath()).toBe("/");
});

it("ignores damaged and unavailable browser storage", () => {
  localStorage.setItem("batfish-entry-preference", "unknown");
  expect(preferredEntryPath()).toBe("/");
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  expect(preferredEntryPath()).toBe("/");
  expect(() => chooseEntry("leader")).not.toThrow();
});
