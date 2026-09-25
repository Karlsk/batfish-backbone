import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
export type ResourceContext = {
  networkId: string | null;
  snapshotId: string | null;
};
export const resourceKey = (
  identity: string | null,
  context: ResourceContext,
  operation: string,
  parameters: unknown = {},
  resultId: string | null = null,
) =>
  [
    "resource",
    identity,
    context.networkId,
    context.snapshotId,
    resultId,
    operation,
    parameters,
  ] as const;
export type Selection = { id: string; name: string };
type ContextState = {
  network: Selection | null;
  snapshot: Selection | null;
  selectNetwork: (value: Selection | null) => Promise<boolean>;
  selectSnapshot: (
    value: (Selection & { networkId: string }) | null,
  ) => Promise<boolean>;
  registerGuard: (guard: () => Promise<boolean>) => () => void;
};
const Context = createContext<ContextState | null>(null);
export function ContextProvider({ children }: PropsWithChildren) {
  const [network, setNetwork] = useState<Selection | null>(null);
  const [snapshot, setSnapshot] = useState<Selection | null>(null);
  const guards = useRef(new Set<() => Promise<boolean>>());
  const version = useRef(0);
  const networkRef = useRef(network);
  networkRef.current = network;
  const registerGuard = useCallback((guard: () => Promise<boolean>) => {
    guards.current.add(guard);
    return () => {
      guards.current.delete(guard);
    };
  }, []);
  const value = useMemo(
    () => ({
      network,
      snapshot,
      registerGuard,
      selectNetwork: async (next: Selection | null) => {
        if (next?.id === network?.id) return true;
        const request = ++version.current;
        for (const guard of guards.current) if (!(await guard())) return false;
        if (request !== version.current) return false;
        networkRef.current = next;
        setNetwork(next);
        setSnapshot(null);
        return true;
      },
      selectSnapshot: async (
        next: (Selection & { networkId: string }) | null,
      ) => {
        if (next && next.networkId !== networkRef.current?.id)
          throw new Error("Snapshot does not belong to the selected network");
        if (next?.id === snapshot?.id) return true;
        const request = ++version.current;
        for (const guard of guards.current) if (!(await guard())) return false;
        if (
          request !== version.current ||
          (next && next.networkId !== networkRef.current?.id)
        )
          return false;
        setSnapshot(next);
        return true;
      },
    }),
    [network, snapshot, registerGuard],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useResourceContext() {
  const value = useContext(Context);
  if (!value) throw new Error("ContextProvider is required");
  return value;
}
