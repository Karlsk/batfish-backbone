import { Drawer } from "antd";
import { useQuery, type QueryKey } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ErrorState, LoadingState } from "./States";
export function DetailsDrawer<T>({
  open,
  title,
  onClose,
  queryKey,
  load,
  render,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  queryKey: QueryKey;
  load: (signal: AbortSignal) => Promise<T>;
  render?: (data: T) => ReactNode;
}) {
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => load(signal),
    enabled: open,
  });
  return (
    <Drawer open={open} title={title} onClose={onClose} size={560}>
      {open &&
        (query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} retry={() => void query.refetch()} />
        ) : render ? (
          render(query.data)
        ) : (
          <pre className="raw-detail">
            {JSON.stringify(query.data, null, 2)}
          </pre>
        ))}
    </Drawer>
  );
}
