import { useSyncExternalStore } from "react";
import type { components } from "../api/schema";
export type Session = components["schemas"]["SessionInfo"];
let current: Session | null = null;
let generation = 0;
const listeners = new Set<() => void>();
const identityListeners = new Set<() => void>();
export function getSession() {
  return current;
}
export function sessionGeneration() {
  return generation;
}
export function setSession(next: Session | null) {
  const identityChanged =
    current?.user_id !== next?.user_id || current?.role !== next?.role;
  current = next;
  generation++;
  if (identityChanged) identityListeners.forEach((fn) => fn());
  listeners.forEach((fn) => fn());
}
export function onIdentityChange(fn: () => void) {
  identityListeners.add(fn);
  return () => {
    identityListeners.delete(fn);
  };
}
export function useSession() {
  return useSyncExternalStore((fn) => {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, getSession);
}
