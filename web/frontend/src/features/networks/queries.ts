import { useInfiniteQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../api/client";
import { resourceKey } from "../../app/context";
import { useSession } from "../../app/session";
export function useNetworks() {
  const session = useSession();
  return useInfiniteQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: null, snapshotId: null },
      "networks",
    ),
    queryFn: ({ pageParam, signal }) =>
      unwrap(
        api.GET("/api/v1/networks", {
          signal,
          params: { query: { offset: pageParam, limit: 50 } },
        }),
      ),
    initialPageParam: 0,
    getNextPageParam: (page) =>
      page.offset + page.items.length < page.total
        ? page.offset + page.items.length
        : undefined,
    enabled: !!session && !session.must_change_password,
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) =>
        page.items.some((n) => n.sync_state === "deleting"),
      )
        ? 2000
        : false,
  });
}
export function useSnapshots(networkId: string | null) {
  const session = useSession();
  return useInfiniteQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId, snapshotId: null },
      "snapshots",
    ),
    queryFn: ({ pageParam, signal }) =>
      unwrap(
        api.GET("/api/v1/networks/{network_id}/snapshots", {
          signal,
          params: {
            path: { network_id: networkId! },
            query: { offset: pageParam, limit: 50 },
          },
        }),
      ),
    initialPageParam: 0,
    getNextPageParam: (page) =>
      page.offset + page.items.length < page.total
        ? page.offset + page.items.length
        : undefined,
    enabled: !!session && !!networkId && !session.must_change_password,
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) =>
        page.items.some(
          (s) =>
            s.status === "queued" ||
            s.status === "initializing" ||
            s.status === "deleting",
        ),
      )
        ? 2000
        : false,
  });
}
