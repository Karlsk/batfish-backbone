import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { resourceKey } from "./context";
describe("resource isolation", () => {
  it("a late old snapshot cannot replace the current snapshot", async () => {
    let resolveOld!: (value: string) => void;
    const old = new Promise<string>((resolve) => {
      resolveOld = resolve;
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    function Result({ snapshot }: { snapshot: string }) {
      const result = useQuery({
        queryKey: resourceKey(
          "user",
          { networkId: "network", snapshotId: snapshot },
          "nodes",
          {},
        ),
        queryFn: () => (snapshot === "old" ? old : Promise.resolve("新快照")),
      });
      return <div>{result.data ?? "加载中"}</div>;
    }
    const view = render(
      <QueryClientProvider client={client}>
        <Result snapshot="old" />
      </QueryClientProvider>,
    );
    view.rerender(
      <QueryClientProvider client={client}>
        <Result snapshot="new" />
      </QueryClientProvider>,
    );
    await screen.findByText("新快照");
    await act(async () => {
      resolveOld("旧快照");
      await old;
    });
    expect(screen.queryByText("旧快照")).toBeNull();
    expect(screen.getByText("新快照")).toBeTruthy();
  });
});
