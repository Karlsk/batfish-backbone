import {
  createContext,
  useContext,
  useMemo,
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
type Selection = { id: string; name: string };
type ContextState = {
  network: Selection | null;
  snapshot: Selection | null;
  selectNetwork: (value: Selection | null) => void;
  selectSnapshot: (value: (Selection & { networkId: string }) | null) => void;
};
const Context = createContext<ContextState | null>(null);
export function ContextProvider({ children }: PropsWithChildren) {
  const [network, setNetwork] = useState<Selection | null>(null);
  const [snapshot, setSnapshot] = useState<Selection | null>(null);
  const value = useMemo(
    () => ({
      network,
      snapshot,
      selectNetwork: (next: Selection | null) => {
        setNetwork(next);
        if (next?.id !== network?.id) setSnapshot(null);
      },
      selectSnapshot: (next: (Selection & { networkId: string }) | null) => {
        if (next && next.networkId !== network?.id)
          throw new Error("Snapshot does not belong to the selected network");
        setSnapshot(next);
      },
    }),
    [network, snapshot],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useResourceContext() {
  const value = useContext(Context);
  if (!value) throw new Error("ContextProvider is required");
  return value;
}
