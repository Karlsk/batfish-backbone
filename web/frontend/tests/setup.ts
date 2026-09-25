import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
afterEach(cleanup);
Object.defineProperty(window, "matchMedia", {
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })),
});
window.getComputedStyle = new Proxy(window.getComputedStyle, {
  apply(target, thisArg, args) {
    return Reflect.apply(target, thisArg, [args[0]]);
  },
});
